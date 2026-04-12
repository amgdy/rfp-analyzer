"""Step 2: Extract Content from Documents."""

import streamlit as st
import asyncio
import time
import uuid

from services.utils import format_duration, clean_extracted_text
from services.document_processor import ExtractionService
from services.processing_queue import ProcessingQueue, QueueItemStatus
from services.token_utils import estimate_token_count, MODEL_CONTEXT_WINDOW
from services.logging_config import get_logger
from ui.styles import STEP_ANIMATION_CSS
from ui.components import render_step_indicator

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Mermaid diagram for chunked processing (shown for large documents)
# ---------------------------------------------------------------------------

_CHUNKING_MERMAID = """
```mermaid
flowchart TD
    A["📄 Large Document<br/>(>MAX_TOKENS tokens)"] --> B["🔢 Estimate Token Count"]
    B --> C{{"Exceeds context<br/>window?"}}
    C -- No --> D["✅ Process in single call"]
    C -- Yes --> E["✂️ Split by headings /<br/>paragraphs"]
    E --> F["📦 Chunk 1"]
    E --> G["📦 Chunk 2"]
    E --> H["📦 Chunk N"]
    F --> I["🤖 LLM Evaluation"]
    G --> I
    H --> I
    I --> J["🔀 Merge Results<br/>(best score per criterion)"]
    J --> K["📊 Final Evaluation"]
```
"""


def render_step2():
    """Step 2: Extract Content from Documents."""
    render_step_indicator(current_step=2)

    st.header("Step 2: Extract Content")
    st.markdown("Extract text content from uploaded documents using Azure AI services.")

    # Show uploaded files summary
    col1, col2 = st.columns(2)
    with col1:
        if st.session_state.rfp_file:
            st.info(f"📄 RFP: {st.session_state.rfp_file['name']}")
    with col2:
        if st.session_state.proposal_files:
            st.info(f"📝 Proposals: {len(st.session_state.proposal_files)} file(s)")

    # Show configuration summary
    st.markdown("---")
    st.subheader("⚙️ Current Configuration")

    config_col1, config_col2 = st.columns(2)
    with config_col1:
        service_name = "Content Understanding" if st.session_state.extraction_service == ExtractionService.CONTENT_UNDERSTANDING else "Document Intelligence"
        st.metric("Extraction Service", service_name)
    with config_col2:
        st.metric("Analysis Depth", st.session_state.reasoning_effort.title())

    # Global criteria preview
    if st.session_state.global_criteria:
        with st.expander("📋 Global Evaluation Criteria", expanded=False):
            st.markdown(st.session_state.global_criteria)

    st.markdown("---")

    # Check if content has been extracted
    if st.session_state.rfp_content and st.session_state.proposal_contents:
        st.success("✅ All documents have been processed!")

        # Show extraction queue summary if available
        if st.session_state.extraction_queue:
            queue = st.session_state.extraction_queue
            with st.expander("📊 Extraction Summary", expanded=False):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Documents", len(queue.items))
                with col2:
                    st.metric("Total Time", format_duration(queue.get_total_duration()))
                with col3:
                    st.metric("Avg per Doc", format_duration(queue.get_average_item_duration()))

                for item in queue.items:
                    if item.duration:
                        st.markdown(f"• **{item.name}**: `{format_duration(item.duration)}`")

        # Show extracted content previews (cleaned for executive display)
        _render_content_previews()

        if st.button(
            "Continue to Step 3: Review Criteria →",
            type="primary",
            width="stretch",
            disabled=st.session_state.is_processing
        ):
            logger.info("User proceeding to Step 3 - Criteria Review")
            st.session_state.step = 3
            st.rerun()
    else:
        # Run extraction
        if st.button(
            "🔍 Extract Document Content",
            type="primary",
            width="stretch",
            disabled=st.session_state.is_processing
        ):
            logger.info("User starting document extraction")
            st.session_state.is_processing = True
            run_extraction_pipeline()

    # Navigation
    st.markdown("---")
    if st.button("⬅️ Back to Step 1", disabled=st.session_state.is_processing):
        logger.info("User navigating back to Step 1")
        st.session_state.step = 1
        st.rerun()


def _render_content_previews():
    """Render cleaned previews of extracted document content.

    Shows a mermaid processing diagram when a document's estimated
    token count exceeds the configured model context window.
    """
    rfp_text = st.session_state.rfp_content or ""
    rfp_tokens = estimate_token_count(rfp_text)

    with st.expander("📄 RFP Content Preview", expanded=False):
        st.caption(f"Estimated tokens: **{rfp_tokens:,}** / Context window: **{MODEL_CONTEXT_WINDOW:,}**")
        if rfp_tokens > MODEL_CONTEXT_WINDOW:
            st.warning(
                "⚠️ This document exceeds the model context window and will be "
                "processed using chunked evaluation."
            )
            st.markdown(
                _CHUNKING_MERMAID.replace("MAX_TOKENS", f"{MODEL_CONTEXT_WINDOW:,}")
            )
        cleaned = clean_extracted_text(rfp_text)
        preview = cleaned[:2000] + "…" if len(cleaned) > 2000 else cleaned
        st.markdown(preview)

    with st.expander("📝 Proposal Contents Preview", expanded=False):
        for filename, content in st.session_state.proposal_contents.items():
            tokens = estimate_token_count(content)
            st.markdown(f"### {filename}")
            st.caption(f"Estimated tokens: **{tokens:,}** / Context window: **{MODEL_CONTEXT_WINDOW:,}**")
            if tokens > MODEL_CONTEXT_WINDOW:
                st.warning(
                    "⚠️ This document exceeds the model context window and will be "
                    "processed using chunked evaluation."
                )
                st.markdown(
                    _CHUNKING_MERMAID.replace("MAX_TOKENS", f"{MODEL_CONTEXT_WINDOW:,}")
                )
            cleaned = clean_extracted_text(content)
            preview = cleaned[:1000] + "…" if len(cleaned) > 1000 else cleaned
            st.markdown(preview)
            st.markdown("---")


def run_extraction_pipeline():
    """Run the document extraction pipeline with parallel processing and live progress."""
    from services.pipelines import process_document

    extraction_service = st.session_state.extraction_service
    logger.info("====== EXTRACTION PIPELINE STARTED (Service: %s) ======", extraction_service.value)
    pipeline_start = time.time()

    # Inject animation CSS
    st.markdown(STEP_ANIMATION_CSS, unsafe_allow_html=True)

    # Create extraction queue
    extraction_queue = ProcessingQueue(name="Document Extraction")

    # Add RFP to queue with unique request ID
    rfp_file = st.session_state.rfp_file
    rfp_request_id = str(uuid.uuid4())[:8]
    extraction_queue.add_item(
        id="rfp",
        name=rfp_file['name'],
        item_type="rfp",
        metadata={
            "filename": rfp_file["name"],
            "size": len(rfp_file["bytes"]),
            "request_id": rfp_request_id
        }
    )
    logger.info("Queued RFP for extraction: %s (request_id: %s)", rfp_file['name'], rfp_request_id)

    # Add proposals to queue with unique request IDs
    for i, proposal_file in enumerate(st.session_state.proposal_files):
        proposal_request_id = str(uuid.uuid4())[:8]
        extraction_queue.add_item(
            id=f"proposal_{i}",
            name=proposal_file['name'],
            item_type="proposal",
            metadata={
                "filename": proposal_file["name"],
                "size": len(proposal_file["bytes"]),
                "request_id": proposal_request_id
            }
        )
        logger.info("Queued proposal for extraction: %s (request_id: %s)",
                   proposal_file['name'], proposal_request_id)

    extraction_queue.start()
    st.session_state.extraction_queue = extraction_queue

    # UI Setup - single placeholder for live updates
    st.subheader("📄 Extracting Documents")

    # Create a single placeholder that we'll update
    status_placeholder = st.empty()

    try:
        all_files = [rfp_file] + st.session_state.proposal_files
        total_files = len(all_files)

        # Mark all items as processing
        for item in extraction_queue.items:
            item.start()

        # Define async function for parallel processing
        async def process_all_documents():
            tasks = []
            for file_data in all_files:
                task = process_document(
                    file_data["bytes"],
                    file_data["name"],
                    extraction_service
                )
                tasks.append(task)
            return await asyncio.gather(*tasks, return_exceptions=True)

        # Start timer update loop in a separate display
        def render_status():
            """Render the current queue status."""
            with status_placeholder.container():
                # Overall progress
                elapsed = time.time() - pipeline_start
                st.markdown(f"**⏱️ Elapsed: `{format_duration(elapsed)}`** | Processing {total_files} documents in parallel...")

                # Progress bar
                progress = extraction_queue.get_progress()
                st.progress(progress["percentage"] / 100)

                # Items status
                for item in extraction_queue.items:
                    icon = item.get_status_icon()
                    elapsed_time = format_duration(item.get_elapsed_time()) if item.start_time else "-"

                    if item.item_type == "rfp":
                        label = f"📄 RFP: {item.name}"
                    else:
                        label = f"📝 Proposal: {item.name}"

                    if item.status == QueueItemStatus.COMPLETED:
                        st.success(f"{icon} {label} — `{elapsed_time}`")
                    elif item.status == QueueItemStatus.PROCESSING:
                        st.info(f"{icon} {label} — Processing... `{elapsed_time}`")
                    elif item.status == QueueItemStatus.FAILED:
                        st.error(f"{icon} {label} — Failed")
                    else:
                        st.warning(f"{icon} {label} — Waiting...")

        # Initial render
        render_status()

        # Run parallel processing
        results = asyncio.run(process_all_documents())

        # Process results and update queue
        extracted_results = []
        for i, result in enumerate(results):
            item_id = "rfp" if i == 0 else f"proposal_{i-1}"
            item = extraction_queue.get_item(item_id)

            if isinstance(result, Exception):
                item.fail(str(result))
                logger.error("Failed to extract document %d: %s", i, str(result))
                extracted_results.append((None, 0))
            else:
                content, duration = result
                item.complete(result=content)
                extracted_results.append((content, duration))
                logger.info("Extracted document %d in %.2fs", i, duration)

        # Final render
        render_status()

        # Check for failures
        failed_items = extraction_queue.get_failed_items()
        if failed_items:
            raise Exception(f"Failed to extract {len(failed_items)} document(s)")

        # Store results
        rfp_content, rfp_duration = extracted_results[0]
        st.session_state.rfp_content = rfp_content
        st.session_state.step_durations["rfp_processing"] = rfp_duration

        proposal_contents = {}
        for i, file_data in enumerate(st.session_state.proposal_files):
            content, duration = extracted_results[i + 1]
            proposal_contents[file_data["name"]] = content
            st.session_state.step_durations[f"proposal_{i}_processing"] = duration

        st.session_state.proposal_contents = proposal_contents

        extraction_queue.finish()
        st.session_state.extraction_queue = extraction_queue

        total_duration = time.time() - pipeline_start
        st.session_state.step_durations["extraction_total"] = total_duration

        logger.info("====== EXTRACTION PIPELINE COMPLETED in %.2fs ======", total_duration)

        # Show completion message
        st.success(f"✅ **All {total_files} documents extracted in {format_duration(total_duration)}!**")

        st.session_state.is_processing = False
        time.sleep(1)
        st.rerun()

    except Exception as e:
        logger.error("Extraction pipeline failed: %s", str(e))
        extraction_queue.finish()
        st.session_state.extraction_queue = extraction_queue
        st.session_state.is_processing = False
        st.error(f"❌ Error during extraction: {str(e)}")
