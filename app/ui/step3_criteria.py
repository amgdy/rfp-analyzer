"""Step 3: Review Evaluation Criteria.

Extracts scoring criteria from the RFP using AI and displays them for
user review before proceeding to proposal scoring.
"""

import streamlit as st
import asyncio
import json
import time

from services.utils import format_duration
from services.logging_config import get_logger
from services.telemetry import get_tracer
from ui.styles import STEP_ANIMATION_CSS
from ui.components import render_step_indicator

logger = get_logger(__name__)
tracer = get_tracer(__name__)


def render_step3():
    """Step 3: Review Evaluation Criteria."""
    render_step_indicator(current_step=3)

    st.header("Step 3: Review Criteria")
    st.markdown(
        "AI-extracted evaluation criteria from your RFP. "
        "Review the criteria and weights that will be used to score vendor proposals."
    )

    # Show files summary
    col1, col2 = st.columns(2)
    with col1:
        if st.session_state.rfp_file:
            st.info(f"📄 RFP: {st.session_state.rfp_file['name']}")
    with col2:
        if st.session_state.proposal_files:
            st.info(f"📝 Proposals: {len(st.session_state.proposal_files)} file(s)")

    # Show global criteria if user provided any
    if st.session_state.global_criteria:
        with st.expander("📋 Your Additional Criteria", expanded=False):
            st.markdown(st.session_state.global_criteria)
            st.caption(
                "These criteria will be combined with the AI-extracted criteria "
                "from the RFP document."
            )

    # Check if criteria have already been extracted
    if st.session_state.extracted_criteria:
        _render_criteria_review()

        # Download criteria as JSON
        criteria_json = json.dumps(
            st.session_state.extracted_criteria, indent=2, ensure_ascii=False,
        )
        st.download_button(
            label="📥 Download Scoring Criteria (JSON)",
            data=criteria_json,
            file_name="extracted_scoring_criteria.json",
            mime="application/json",
            use_container_width=True,
        )

        if st.button(
            "Continue to Step 4: Score Proposals →",
            type="primary",
            use_container_width=True,
            disabled=st.session_state.is_processing,
        ):
            logger.info("User proceeding to Step 4 - Scoring")
            st.session_state.step = 4
            st.rerun()
    else:
        # Explain what will happen
        with st.expander("🤖 How Criteria Extraction Works", expanded=True):
            st.info(
                "**The AI Criteria Extraction Agent will:**\n\n"
                "1. Analyze your RFP document structure and content\n"
                "2. Identify all explicit and implied evaluation criteria\n"
                "3. Assign weight percentages (totaling 100%) based on RFP emphasis\n"
                "4. Provide scoring guidance for each criterion\n\n"
                "You'll be able to review everything before scoring begins."
            )

        if st.button(
            "🔍 Extract Evaluation Criteria",
            type="primary",
            use_container_width=True,
            disabled=st.session_state.is_processing,
        ):
            logger.info("User starting criteria extraction")
            st.session_state.is_processing = True
            _run_criteria_extraction()

    # Navigation
    st.markdown("---")
    if st.button("⬅️ Back to Step 2", disabled=st.session_state.is_processing):
        logger.info("User navigating back to Step 2")
        st.session_state.step = 2
        st.rerun()


def _render_criteria_review():
    """Render the extracted criteria for user review."""
    criteria_data = st.session_state.extracted_criteria

    rfp_title = criteria_data.get("rfp_title", "Unknown RFP")
    rfp_summary = criteria_data.get("rfp_summary", "")
    criteria_list = criteria_data.get("criteria", [])
    extraction_notes = criteria_data.get("extraction_notes", "")

    # Summary header
    overall_confidence = criteria_data.get("overall_confidence", 0.8)
    st.success(f"✅ **{len(criteria_list)} evaluation criteria** extracted from the RFP")

    # RFP Info
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("RFP Title", rfp_title[:30] + "..." if len(rfp_title) > 30 else rfp_title)
    with col2:
        st.metric("Total Criteria", str(len(criteria_list)))
    with col3:
        total_weight = sum(c.get("weight", 0) for c in criteria_list)
        st.metric("Total Weight", f"{total_weight:.1f}%")
    with col4:
        conf_pct = f"{overall_confidence:.0%}"
        if overall_confidence >= 0.9:
            st.metric("Confidence", conf_pct, delta="High", delta_color="normal")
        elif overall_confidence >= 0.7:
            st.metric("Confidence", conf_pct, delta="Good", delta_color="normal")
        else:
            st.metric("Confidence", conf_pct, delta="Low", delta_color="inverse")

    if rfp_summary:
        st.markdown(f"**RFP Summary:** {rfp_summary}")

    st.markdown("---")

    # Criteria breakdown by category
    st.subheader("📊 Criteria Overview")

    # Group by category
    categories: dict[str, list] = {}
    for c in criteria_list:
        cat = c.get("category", "Other")
        categories.setdefault(cat, []).append(c)

    # Category weight summary
    if not categories:
        st.info("No criteria categories found.")
        return
    cat_cols = st.columns(min(len(categories), 4))
    for i, (cat_name, cat_criteria) in enumerate(categories.items()):
        col_idx = i % min(len(categories), 4)
        cat_weight = sum(c.get("weight", 0) for c in cat_criteria)
        with cat_cols[col_idx]:
            st.metric(
                f"📁 {cat_name}",
                f"{cat_weight:.1f}%",
                delta=f"{len(cat_criteria)} criteria",
                delta_color="off",
            )

    st.markdown("---")

    # Detailed criteria list
    st.subheader("📋 Evaluation Criteria Details")
    st.markdown(
        "Each criterion below will be used to score vendor proposals. "
        "The weight determines how much each criterion contributes to the final score."
    )

    for c in criteria_list:
        criterion_id = c.get("criterion_id", "")
        name = c.get("name", "Unknown")
        description = c.get("description", "")
        category = c.get("category", "Other")
        weight = c.get("weight", 0)
        guidance = c.get("evaluation_guidance", "")
        confidence = c.get("confidence", 0.8)

        # Confidence badge
        if confidence >= 0.9:
            conf_badge = "🟢"
        elif confidence >= 0.7:
            conf_badge = "🟡"
        else:
            conf_badge = "🔴"

        # Color coding by weight
        if weight >= 20:
            weight_icon = "🔴"
            weight_label = "High Impact"
        elif weight >= 10:
            weight_icon = "🟡"
            weight_label = "Medium Impact"
        else:
            weight_icon = "🟢"
            weight_label = "Standard"

        with st.expander(
            f"{weight_icon} **{criterion_id}: {name}** — Weight: {weight:.1f}% ({weight_label}) {conf_badge} {confidence:.0%}",
            expanded=False,
        ):
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.markdown(f"**Category:** {category}")
                st.markdown(f"**Description:** {description}")
            with col2:
                st.metric("Weight", f"{weight:.1f}%")
            with col3:
                conf_label = "High" if confidence >= 0.9 else "Good" if confidence >= 0.7 else "Low"
                st.metric("Confidence", f"{confidence:.0%}", delta=conf_label,
                          delta_color="normal" if confidence >= 0.7 else "inverse")

            if guidance:
                st.markdown("**Scoring Guidance:**")
                st.markdown(f"_{guidance}_")

    # Extraction notes
    if extraction_notes:
        with st.expander("📝 Extraction Notes", expanded=False):
            st.caption(extraction_notes)

    # Show extraction timing if available
    criteria_duration = st.session_state.step_durations.get("criteria_extraction", 0)
    if criteria_duration:
        st.caption(f"⏱️ Criteria extracted in {format_duration(criteria_duration)}")


def _run_criteria_extraction():
    """Run the AI criteria extraction pipeline."""
    from services.pipelines import extract_criteria

    reasoning_effort = st.session_state.reasoning_effort
    global_criteria = st.session_state.global_criteria
    rfp_content = st.session_state.rfp_content

    logger.info("====== CRITERIA EXTRACTION STARTED (Effort: %s) ======", reasoning_effort)
    pipeline_start = time.time()

    with tracer.start_as_current_span("criteria_extraction_pipeline") as pipeline_span:
        pipeline_span.set_attribute("pipeline.type", "criteria_extraction")
        pipeline_span.set_attribute("pipeline.reasoning_effort", reasoning_effort)
        pipeline_span.set_attribute("pipeline.has_global_criteria", bool(global_criteria))

        # Inject animation CSS
        st.markdown(STEP_ANIMATION_CSS, unsafe_allow_html=True)

        st.subheader("🔍 Extracting Evaluation Criteria")
        status_placeholder = st.empty()

        try:
            with status_placeholder.container():
                st.info("🤖 AI is analyzing the RFP document to extract evaluation criteria...")
                progress_bar = st.progress(0)

            # Run extraction
            criteria_dict, duration = asyncio.run(
                extract_criteria(
                    rfp_content,
                    global_criteria=global_criteria,
                    reasoning_effort=reasoning_effort,
                )
            )

            criteria_count = len(criteria_dict.get("criteria", []))

            if criteria_count == 0:
                # No criteria found — likely not a valid RFP document
                with status_placeholder.container():
                    st.progress(100)
                    st.error(
                        "❌ **No evaluation criteria could be extracted.**\n\n"
                        "The uploaded file does not appear to be a valid RFP document, "
                        "or it does not contain identifiable evaluation criteria.\n\n"
                        "Please go back to **Step 1** and upload a proper RFP file."
                    )
                pipeline_span.set_attribute("pipeline.status", "no_criteria")
                logger.warning(
                    "Criteria extraction returned 0 criteria — file may not be a valid RFP"
                )
                st.session_state.is_processing = False
                return

            with status_placeholder.container():
                st.progress(100)
                st.success(
                    f"✅ Extracted **{criteria_count} criteria** in "
                    f"{format_duration(duration)}"
                )

            # Store results
            st.session_state.extracted_criteria = criteria_dict
            st.session_state.step_durations["criteria_extraction"] = duration

            # Persist criteria state to blob
            try:
                from services.session_state_manager import get_session_manager
                session_id = st.session_state.session_id
                mgr = get_session_manager(session_id)
                mgr.load()
                mgr.save_criteria(criteria_data=criteria_dict, duration_seconds=duration)
            except Exception as state_err:
                logger.debug("Failed to save criteria state: %s", str(state_err))

            total_duration = time.time() - pipeline_start
            pipeline_span.set_attribute("pipeline.criteria_count", criteria_count)
            pipeline_span.set_attribute("pipeline.duration_seconds", total_duration)
            pipeline_span.set_attribute("pipeline.status", "success")
            logger.info(
                "====== CRITERIA EXTRACTION COMPLETED in %.2fs - %d criteria ======",
                total_duration,
                criteria_count,
            )

            st.session_state.is_processing = False
            time.sleep(1)
            st.rerun()

        except Exception as e:
            pipeline_span.record_exception(e)
            pipeline_span.set_attribute("pipeline.status", "failed")
            logger.error("Criteria extraction failed: %s", str(e))
            st.session_state.is_processing = False
            st.error(f"❌ Error during criteria extraction: {str(e)}")
