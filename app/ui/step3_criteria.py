"""Step 3: Review Evaluation Criteria.

Extracts scoring criteria from the RFP using AI and displays them for
user review before proceeding to proposal scoring.
"""

import streamlit as st
import asyncio
import time

from services.utils import format_duration
from services.logging_config import get_logger
from ui.styles import STEP_ANIMATION_CSS
from ui.components import render_step_indicator

logger = get_logger(__name__)


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

        if st.button(
            "Continue to Step 4: Score Proposals →",
            type="primary",
            width="stretch",
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
            width="stretch",
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
    st.success(f"✅ **{len(criteria_list)} evaluation criteria** extracted from the RFP")

    # RFP Info
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("RFP Title", rfp_title[:30] + "..." if len(rfp_title) > 30 else rfp_title)
    with col2:
        st.metric("Total Criteria", str(len(criteria_list)))
    with col3:
        total_weight = sum(c.get("weight", 0) for c in criteria_list)
        st.metric("Total Weight", f"{total_weight:.1f}%")

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
            f"{weight_icon} **{criterion_id}: {name}** — Weight: {weight:.1f}% ({weight_label})",
            expanded=False,
        ):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"**Category:** {category}")
                st.markdown(f"**Description:** {description}")
            with col2:
                st.metric("Weight", f"{weight:.1f}%")

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

        with status_placeholder.container():
            progress_bar = st.progress(100)
            criteria_count = len(criteria_dict.get("criteria", []))
            st.success(
                f"✅ Extracted **{criteria_count} criteria** in "
                f"{format_duration(duration)}"
            )

        # Store results
        st.session_state.extracted_criteria = criteria_dict
        st.session_state.step_durations["criteria_extraction"] = duration

        total_duration = time.time() - pipeline_start
        logger.info(
            "====== CRITERIA EXTRACTION COMPLETED in %.2fs - %d criteria ======",
            total_duration,
            len(criteria_dict.get("criteria", [])),
        )

        st.session_state.is_processing = False
        time.sleep(1)
        st.rerun()

    except Exception as e:
        logger.error("Criteria extraction failed: %s", str(e))
        st.session_state.is_processing = False
        st.error(f"❌ Error during criteria extraction: {str(e)}")
