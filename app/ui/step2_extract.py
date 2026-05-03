"""Step 2: Extract Content from Documents."""

import streamlit as st
import asyncio
import time
import uuid

from services.utils import format_duration, clean_extracted_text
from services.document_processor import ExtractionService, requires_ai_extraction
from services.processing_queue import ProcessingQueue, QueueItemStatus
from services.token_utils import estimate_token_count, MODEL_CONTEXT_WINDOW
from services.logging_config import get_logger
from services.telemetry import get_tracer
from ui.styles import STEP_ANIMATION_CSS
from ui.components import render_step_indicator

logger = get_logger(__name__)
tracer = get_tracer(__name__)


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


def _load_extracted_content_from_blob():
    """Try to load previously extracted content from blob storage into session state.

    This handles the case where session state is lost (e.g., page reload) but
    the extracted content is still available in blob storage.
    """
    session_id = st.session_state.session_id
    if not session_id:
        return

    # Skip if both already loaded
    if st.session_state.rfp_content and st.session_state.proposal_contents:
        return

    try:
        from services.blob_storage_client import get_blob_storage_client
        client = get_blob_storage_client()

        # Load RFP content if missing
        if not st.session_state.rfp_content and st.session_state.rfp_file:
            rfp_name = st.session_state.rfp_file["name"]
            content = client.get_extracted_rfp(session_id, rfp_name)
            if content:
                st.session_state.rfp_content = content
                logger.info("Loaded RFP extracted content from blob: %s", rfp_name)

        # Load proposal contents if missing
        if not st.session_state.proposal_contents and st.session_state.proposal_files:
            proposal_contents = {}
            for pf in st.session_state.proposal_files:
                content = client.get_extracted_proposal(session_id, pf["name"])
                if content:
                    proposal_contents[pf["name"]] = content
            if proposal_contents:
                st.session_state.proposal_contents = proposal_contents
                logger.info("Loaded %d proposal extracted contents from blob", len(proposal_contents))
    except Exception as e:
        logger.debug("Could not load extracted content from blob: %s", str(e))


def render_step2():
    """Step 2: Extract Content from Documents."""
    render_step_indicator(current_step=2)

    st.header("Step 2: Extract Content")
    st.markdown("Extract text content from uploaded documents using Azure AI services.")

    # Try to load extracted content from blob (handles page reload)
    _load_extracted_content_from_blob()

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
            use_container_width=True,
            disabled=st.session_state.is_processing
        ):
            logger.info("User proceeding to Step 3 - Criteria Review")
            st.session_state.step = 3
            st.rerun()
    else:
        # Show file type categorization before extraction
        _render_file_categorization()

        # Run extraction
        if st.button(
            "🔍 Extract Document Content",
            type="primary",
            use_container_width=True,
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


def _render_file_categorization():
    """Show users which files will use AI extraction vs direct read."""
    all_files = []
    if st.session_state.rfp_file:
        all_files.append(st.session_state.rfp_file["name"])
    all_files.extend(f["name"] for f in (st.session_state.proposal_files or []))

    ai_files = [f for f in all_files if requires_ai_extraction(f)]
    text_files = [f for f in all_files if not requires_ai_extraction(f)]

    if ai_files:
        st.info(
            f"🔍 **{len(ai_files)} file(s) require AI extraction:** "
            + ", ".join(f"`{f}`" for f in ai_files)
        )
    if text_files:
        st.success(
            f"📝 **{len(text_files)} file(s) will be read directly** (instant, no AI needed): "
            + ", ".join(f"`{f}`" for f in text_files)
        )


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
    from services.blob_storage_client import get_blob_storage_client

    extraction_service = st.session_state.extraction_service
    session_id = st.session_state.session_id
    logger.info("====== EXTRACTION PIPELINE STARTED (Service: %s, Session: %s) ======",
                extraction_service.value, session_id)
    pipeline_start = time.time()

    with tracer.start_as_current_span("extraction_pipeline") as pipeline_span:
        pipeline_span.set_attribute("pipeline.type", "extraction")
        pipeline_span.set_attribute("pipeline.extraction_service", extraction_service.value)
        pipeline_span.set_attribute("pipeline.session_id", session_id)
        pipeline_span.set_attribute("pipeline.document_count", 1 + len(st.session_state.proposal_files))

        # Inject animation CSS
        st.markdown(STEP_ANIMATION_CSS, unsafe_allow_html=True)

        # Get blob storage client to download files for extraction
        blob_client = get_blob_storage_client()

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
                "size": rfp_file.get("size", 0),
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
                    "size": proposal_file.get("size", 0),
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
            # Download file bytes from blob storage
            rfp_bytes = blob_client.download_rfp(session_id, rfp_file["name"])
            if rfp_bytes is None:
                raise Exception(f"RFP file not found in storage: {rfp_file['name']}")

            all_file_data = [{"bytes": rfp_bytes, "name": rfp_file["name"]}]
            for proposal_file in st.session_state.proposal_files:
                proposal_bytes = blob_client.download_proposal(session_id, proposal_file["name"])
                if proposal_bytes is None:
                    raise Exception(f"Proposal file not found in storage: {proposal_file['name']}")
                all_file_data.append({"bytes": proposal_bytes, "name": proposal_file["name"]})

            total_files = len(all_file_data)

            # Mark all items as processing
            for item in extraction_queue.items:
                item.start()

            # Define async function for parallel processing
            async def process_all_documents():
                tasks = []
                for file_data in all_file_data:
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
                        is_text = not requires_ai_extraction(item.name)

                        if item.item_type == "rfp":
                            label = f"📄 RFP: {item.name}"
                        else:
                            label = f"📝 Proposal: {item.name}"

                        method = " _(direct read)_" if is_text else " _(AI extraction)_"

                        if item.status == QueueItemStatus.COMPLETED:
                            st.success(f"{icon} {label}{method} — `{elapsed_time}`")
                        elif item.status == QueueItemStatus.PROCESSING:
                            st.info(f"{icon} {label}{method} — Processing... `{elapsed_time}`")
                        elif item.status == QueueItemStatus.FAILED:
                            st.error(f"{icon} {label}{method} — Failed")
                        else:
                            st.warning(f"{icon} {label}{method} — Waiting...")

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

            # Store extracted results to blob storage and session state
            rfp_content, rfp_duration = extracted_results[0]
            blob_client.store_extracted_rfp(session_id, rfp_file["name"], rfp_content)
            st.session_state.rfp_content = rfp_content
            st.session_state.step_durations["rfp_processing"] = rfp_duration

            proposal_contents = {}
            for i, file_data in enumerate(st.session_state.proposal_files):
                content, duration = extracted_results[i + 1]
                blob_client.store_extracted_proposal(session_id, file_data["name"], content)
                proposal_contents[file_data["name"]] = content
                st.session_state.step_durations[f"proposal_{i}_processing"] = duration

            st.session_state.proposal_contents = proposal_contents

            extraction_queue.finish()
            st.session_state.extraction_queue = extraction_queue

            total_duration = time.time() - pipeline_start
            st.session_state.step_durations["extraction_total"] = total_duration
            pipeline_span.set_attribute("pipeline.duration_seconds", total_duration)
            pipeline_span.set_attribute("pipeline.status", "success")

            logger.info("====== EXTRACTION PIPELINE COMPLETED in %.2fs ======", total_duration)

            # Show completion message
            st.success(f"✅ **All {total_files} documents extracted in {format_duration(total_duration)}!**")

            st.session_state.is_processing = False
            time.sleep(1)
            st.rerun()

        except Exception as e:
            pipeline_span.record_exception(e)
            pipeline_span.set_attribute("pipeline.status", "failed")
            logger.error("Extraction pipeline failed: %s", str(e))
            extraction_queue.finish()
            st.session_state.extraction_queue = extraction_queue
            st.session_state.is_processing = False
            st.error("❌ Error during extraction. Please check the logs and try again.")
