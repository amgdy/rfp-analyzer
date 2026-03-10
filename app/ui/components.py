"""Shared UI components for RFP Analyzer."""

import streamlit as st
import json

from services.utils import format_duration
from services.report_generator import (
    generate_score_report,
    generate_score_report_v2,
    generate_pdf_from_markdown,
    PDF_AVAILABLE,
    MARKDOWN_AVAILABLE,
)
from services.document_processor import ExtractionService
from services.logging_config import get_logger

logger = get_logger(__name__)


def render_step_indicator(current_step: int):
    """Render a horizontal wizard-style step progress indicator.

    Args:
        current_step: The current active step (1, 2, or 3).
    """
    steps = [
        (1, "Upload"),
        (2, "Extract"),
        (3, "Evaluate"),
    ]

    step_html_parts = []
    for num, label in steps:
        if num < current_step:
            # Completed
            circle = (
                f'<div style="width:36px;height:36px;border-radius:50%;'
                f'background:#4F46E5;color:#fff;display:flex;align-items:center;'
                f'justify-content:center;font-size:18px;font-weight:700;">✓</div>'
            )
            label_style = "color:#4F46E5;font-weight:600;"
        elif num == current_step:
            # Active
            circle = (
                f'<div style="width:36px;height:36px;border-radius:50%;'
                f'background:#4F46E5;color:#fff;display:flex;align-items:center;'
                f'justify-content:center;font-size:16px;font-weight:700;">{num}</div>'
            )
            label_style = "color:#4F46E5;font-weight:700;"
        else:
            # Upcoming
            circle = (
                f'<div style="width:36px;height:36px;border-radius:50%;'
                f'background:#E5E7EB;color:#9CA3AF;display:flex;align-items:center;'
                f'justify-content:center;font-size:16px;font-weight:600;">{num}</div>'
            )
            label_style = "color:#9CA3AF;font-weight:400;"

        step_html_parts.append(
            f'<div style="display:flex;flex-direction:column;align-items:center;gap:6px;">'
            f'{circle}'
            f'<span style="font-size:13px;{label_style}">{label}</span>'
            f'</div>'
        )

    # Connector lines between steps
    def connector(done: bool) -> str:
        color = "#4F46E5" if done else "#E5E7EB"
        return (
            f'<div style="flex:1;height:3px;background:{color};'
            f'border-radius:2px;margin:18px 8px 0 8px;"></div>'
        )

    html = (
        '<div style="display:flex;align-items:flex-start;justify-content:center;'
        'margin:0 auto 24px auto;max-width:500px;">'
    )
    for i, part in enumerate(step_html_parts):
        html += part
        if i < len(step_html_parts) - 1:
            html += connector(i + 1 < current_step)
    html += '</div>'

    st.markdown(html, unsafe_allow_html=True)


def render_sidebar():
    """Render the sidebar with configuration and navigation."""
    with st.sidebar:
        st.markdown(
            '<p style="font-size:1.5rem;font-weight:700;margin:0 0 4px 0;">'
            '📄 RFP Analyzer</p>',
            unsafe_allow_html=True,
        )
        st.caption("AI-Powered RFP Analysis")
        st.divider()

        if st.session_state.step > 0:
            with st.expander("🔧 Document Extraction", expanded=True):
                service_options = {
                    ExtractionService.DOCUMENT_INTELLIGENCE: "Azure Document Intelligence",
                    ExtractionService.CONTENT_UNDERSTANDING: "Azure Content Understanding"
                }

                service = st.radio(
                    "Extraction service:",
                    options=list(service_options.keys()),
                    index=0 if st.session_state.extraction_service == ExtractionService.DOCUMENT_INTELLIGENCE else 1,
                    format_func=lambda x: service_options[x],
                    help="Choose the Azure service for document text extraction.",
                    disabled=st.session_state.is_processing
                )
                if service != st.session_state.extraction_service:
                    logger.info("Extraction service changed to: %s", service.value)
                    st.session_state.extraction_service = service
                    st.session_state.rfp_content = None
                    st.session_state.proposal_contents = {}
                    st.rerun()

            with st.expander("🧠 Analysis Depth", expanded=True):
                depth_options = {
                    "low": "Standard (~5 mins)",
                    "medium": "Thorough (~10 mins)",
                    "high": "Comprehensive (~15 mins)"
                }
                effort = st.radio(
                    "Analysis depth:",
                    options=["low", "medium", "high"],
                    index=["low", "medium", "high"].index(st.session_state.reasoning_effort),
                    format_func=lambda x: depth_options[x],
                    help="Higher depth = more detailed analysis but longer processing time.",
                    disabled=st.session_state.is_processing
                )
                if effort != st.session_state.reasoning_effort:
                    logger.info("Analysis depth changed to: %s", effort)
                    st.session_state.reasoning_effort = effort
                    st.session_state.evaluation_results = []
                    st.session_state.comparison_results = None
                    st.rerun()

            st.divider()

            # Step indicators
            st.markdown("##### 📍 Progress")
            steps = [
                ("1️⃣", "Upload Documents", st.session_state.step >= 1),
                ("2️⃣", "Configure & Extract", st.session_state.step >= 2),
                ("3️⃣", "Evaluate & Compare", st.session_state.step >= 3),
            ]

            for icon, label, active in steps:
                if active:
                    st.success(f"{icon} {label}")
                else:
                    st.info(f"{icon} {label}")

            st.divider()

            # Reset button
            if st.button("🔄 Start Over", use_container_width=True, disabled=st.session_state.is_processing):
                logger.info("User initiated application reset")
                st.session_state.step = 0
                st.session_state.rfp_file = None
                st.session_state.proposal_files = []
                st.session_state.rfp_content = None
                st.session_state.proposal_contents = {}
                st.session_state.evaluation_results = []
                st.session_state.comparison_results = None
                st.session_state.global_criteria = ""
                st.session_state.extraction_service = ExtractionService.DOCUMENT_INTELLIGENCE
                st.session_state.evaluation_mode = "individual"
                st.session_state.reasoning_effort = "low"
                st.session_state.extraction_queue = None
                st.session_state.scoring_queue = None
                st.session_state.step_durations = {}
                st.session_state.is_processing = False
                st.rerun()
        else:
            st.markdown("##### 👋 Welcome!")
            st.markdown(
                "This tool helps you analyze RFP documents and evaluate "
                "vendor proposals using AI."
            )
            st.markdown(
                "**Features:**\n"
                "- 📄 Document extraction\n"
                "- 🎯 AI-powered scoring\n"
                "- 📊 Multi-vendor comparison\n"
                "- 📥 Export reports"
            )

        st.divider()
        st.caption("Powered by Azure AI Services, Microsoft Foundry & Agent Framework")


def render_results(results: dict):
    """Render the evaluation results in a comprehensive markdown report format."""
    st.markdown("---")

    # Display timing information if available
    if st.session_state.step_durations:
        render_timing_summary(st.session_state.step_durations, results)

    # Quick score summary at the top
    render_score_summary(results)

    # Generate and display the markdown report
    report_md = generate_score_report(results)

    # Display report in tabs
    tab1, tab2 = st.tabs(["📊 Score Report", "📋 Raw Data"])

    with tab1:
        st.markdown(report_md)

    with tab2:
        st.json(results)

    # Download buttons section
    st.markdown("---")
    st.subheader("📥 Download Report")

    response_id = results.get('response_id', 'report')
    supplier_name = results.get('supplier_name', 'vendor').replace(' ', '_')

    col1, col2, col3 = st.columns(3)

    with col1:
        st.download_button(
            label="📄 Download Markdown",
            data=report_md,
            file_name=f"rfp_score_report_{response_id}.md",
            mime="text/markdown",
            use_container_width=True,
            help="Download the report as a Markdown file"
        )

    with col2:
        st.download_button(
            label="📋 Download JSON",
            data=json.dumps(results, indent=2),
            file_name=f"rfp_score_report_{response_id}.json",
            mime="application/json",
            use_container_width=True,
            help="Download the raw data as JSON"
        )

    with col3:
        if PDF_AVAILABLE and MARKDOWN_AVAILABLE:
            pdf_data = generate_pdf_from_markdown(
                report_md,
                title=f"RFP Score Report - {supplier_name}"
            )
            if pdf_data:
                st.download_button(
                    label="📑 Download PDF",
                    data=pdf_data,
                    file_name=f"rfp_score_report_{response_id}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    help="Download the report as a PDF file"
                )
            else:
                st.button(
                    "📑 PDF Generation Failed",
                    disabled=True,
                    use_container_width=True,
                    help="PDF generation encountered an error"
                )
        else:
            st.button(
                "📑 PDF Not Available",
                disabled=True,
                use_container_width=True,
                help="Install 'weasyprint' and 'markdown' packages to enable PDF export"
            )


def render_results_v2(results: dict):
    """Render the V2 multi-agent evaluation results."""
    st.markdown("---")

    # Display timing information if available
    if st.session_state.step_durations:
        render_timing_summary_v2(st.session_state.step_durations, results)

    # Quick score summary
    render_score_summary_v2(results)

    # Generate and display the markdown report
    report_md = generate_score_report_v2(results)

    # Display report in tabs
    tab1, tab2, tab3 = st.tabs(["📊 Score Report", "📋 Extracted Criteria", "📄 Raw Data"])

    with tab1:
        st.markdown(report_md)

    with tab2:
        render_extracted_criteria(results)

    with tab3:
        st.json(results)

    # Download buttons
    st.markdown("---")
    st.subheader("📥 Download Report")

    response_id = results.get('response_id', 'report')
    supplier_name = results.get('supplier_name', 'vendor').replace(' ', '_')

    col1, col2, col3 = st.columns(3)

    with col1:
        st.download_button(
            label="📄 Download Markdown",
            data=report_md,
            file_name=f"rfp_score_report_v2_{response_id}.md",
            mime="text/markdown",
            use_container_width=True
        )

    with col2:
        st.download_button(
            label="📋 Download JSON",
            data=json.dumps(results, indent=2),
            file_name=f"rfp_score_report_v2_{response_id}.json",
            mime="application/json",
            use_container_width=True
        )

    with col3:
        if PDF_AVAILABLE and MARKDOWN_AVAILABLE:
            pdf_data = generate_pdf_from_markdown(report_md, title=f"RFP Score Report V2 - {supplier_name}")
            if pdf_data:
                st.download_button(
                    label="📑 Download PDF",
                    data=pdf_data,
                    file_name=f"rfp_score_report_v2_{response_id}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
            else:
                st.button("📑 PDF Generation Failed", disabled=True, use_container_width=True)
        else:
            st.button("📑 PDF Not Available", disabled=True, use_container_width=True)


def render_timing_summary_v2(durations: dict, results: dict):
    """Render timing summary for V2 multi-agent evaluation."""
    st.subheader("⏱️ Multi Agents Evaluation Timing")

    metadata = results.get("_metadata", {})
    time_saved = durations.get("parallel_time_saved", 0)
    docs_parallel_total = durations.get("docs_parallel_total", 0)

    # Row 1: Document processing
    st.markdown("**Document Processing** (parallel)")
    col1, col2, col3 = st.columns(3)

    with col1:
        rfp_time = durations.get("rfp_processing", 0)
        st.metric(label="📄 RFP Processing", value=format_duration(rfp_time))

    with col2:
        proposal_time = durations.get("proposal_processing", 0)
        st.metric(label="📝 Proposal Processing", value=format_duration(proposal_time))

    with col3:
        st.metric(
            label="⚡ Parallel Total",
            value=format_duration(docs_parallel_total),
            delta=f"-{format_duration(time_saved)} saved" if time_saved > 1 else None,
            delta_color="inverse"
        )

    # Row 2: AI Scoring phases
    st.markdown("**AI Evaluation** (multi agents)")
    col1, col2, col3 = st.columns(3)

    with col1:
        phase1_time = metadata.get("phase1_criteria_extraction_seconds", 0)
        criteria_count = metadata.get("criteria_count", 0)
        st.metric(
            label="🔍 3a. Criteria Extraction",
            value=format_duration(phase1_time),
            delta=f"{criteria_count} criteria" if criteria_count else None,
            delta_color="off"
        )

    with col2:
        phase2_time = metadata.get("phase2_proposal_scoring_seconds", 0)
        st.metric(label="📊 3b. Proposal Scoring", value=format_duration(phase2_time))

    with col3:
        total_time = durations.get("total", 0)
        st.metric(label="⏱️ Total Pipeline", value=format_duration(total_time))

    if metadata:
        with st.expander("🔍 Detailed Timing & Model Info", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"""
                **Evaluation Details:**
                - Version: `{metadata.get('version', 'N/A')}`
                - Type: `{metadata.get('evaluation_type', 'N/A')}`
                - Timestamp: `{metadata.get('evaluation_timestamp', 'N/A')}`
                - Model: `{metadata.get('model_deployment', 'N/A')}`
                - Analysis Depth: `{metadata.get('reasoning_effort', 'N/A')}`
                """)
            with col2:
                st.markdown(f"""
                **Multi Agents Timing:**
                - Criteria Extraction (Agent 1): `{format_duration(metadata.get('phase1_criteria_extraction_seconds', 0))}`
                - Proposal Scoring (Agent 2): `{format_duration(metadata.get('phase2_proposal_scoring_seconds', 0))}`
                - Criteria Found: `{metadata.get('criteria_count', 0)}`
                - Time Saved (parallel docs): `{format_duration(time_saved)}`
                """)

    st.markdown("---")


def render_score_summary_v2(results: dict):
    """Render a visual score summary header for V2."""
    total_score = results.get("total_score", 0)
    grade = results.get("grade", "N/A")
    supplier_name = results.get("supplier_name", "Unknown Vendor")
    recommendation = results.get("recommendation", "No recommendation")
    criteria_count = results.get("_metadata", {}).get("criteria_count", 0)

    # Grade color mapping
    grade_colors = {"A": "green", "B": "blue", "C": "orange", "D": "red", "F": "red"}
    grade_color = grade_colors.get(grade, "gray")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(label="Supplier", value=supplier_name[:20] + "..." if len(supplier_name) > 20 else supplier_name)

    with col2:
        st.metric(label="Total Score", value=f"{total_score:.1f}/100", help="Weighted sum of all criterion scores")

    with col3:
        st.metric(label="Criteria Evaluated", value=str(criteria_count))

    with col4:
        st.markdown(f"""
            <div style="text-align: center; padding: 10px;">
                <p style="font-size: 14px; color: gray; margin: 0;">Grade</p>
                <p style="font-size: 32px; font-weight: bold; color: {grade_color}; margin: 5px 0;">{grade}</p>
            </div>
        """, unsafe_allow_html=True)

    # Recommendation banner
    if "recommend" in recommendation.lower() and "not" not in recommendation.lower():
        st.success(f"✅ **Recommendation:** {recommendation}")
    elif "not recommend" in recommendation.lower():
        st.error(f"❌ **Recommendation:** {recommendation}")
    else:
        st.info(f"ℹ️ **Recommendation:** {recommendation}")

    st.markdown("---")


def render_extracted_criteria(results: dict):
    """Render the extracted criteria from the RFP."""
    extracted = results.get("extracted_criteria", {})
    criteria = extracted.get("criteria", [])

    st.subheader("🔍 Criteria Extracted from RFP")

    if extracted.get("rfp_summary"):
        st.info(f"**RFP Summary:** {extracted.get('rfp_summary')}")

    if criteria:
        st.markdown(f"**Total Criteria:** {len(criteria)} | **Total Weight:** {extracted.get('total_weight', 100)}%")

        # Display as a table
        criteria_data = []
        for c in criteria:
            criteria_data.append({
                "ID": c.get("criterion_id", ""),
                "Name": c.get("name", ""),
                "Category": c.get("category", ""),
                "Weight": f"{c.get('weight', 0):.1f}%",
                "Description": c.get("description", "")[:100] + "..." if len(c.get("description", "")) > 100 else c.get("description", "")
            })

        st.dataframe(criteria_data, use_container_width=True)

        # Detailed view in expander
        with st.expander("📋 Detailed Criteria Descriptions", expanded=False):
            for c in criteria:
                st.markdown(f"""
                ### {c.get('criterion_id', '')}. {c.get('name', '')} ({c.get('weight', 0):.1f}%)

                **Category:** {c.get('category', 'N/A')}

                **Description:** {c.get('description', 'N/A')}

                **Evaluation Guidance:** {c.get('evaluation_guidance', 'N/A')}

                ---
                """)
    else:
        st.warning("No criteria extracted.")

    if extracted.get("extraction_notes"):
        st.caption(f"**Notes:** {extracted.get('extraction_notes')}")


def render_timing_summary(durations: dict, results: dict):
    """Render a timing summary for all evaluation steps."""
    st.subheader("⏱️ Evaluation Timing Summary")

    # Get metadata from results if available
    metadata = results.get("_metadata", {})

    # Check if parallel processing was used
    time_saved = durations.get("parallel_time_saved", 0)
    docs_parallel_total = durations.get("docs_parallel_total", 0)

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        rfp_time = durations.get("rfp_processing", 0)
        st.metric(
            label="📄 RFP Processing",
            value=format_duration(rfp_time),
            help="Time to extract content from RFP document"
        )

    with col2:
        proposal_time = durations.get("proposal_processing", 0)
        st.metric(
            label="📝 Proposal Processing",
            value=format_duration(proposal_time),
            help="Time to extract content from Proposal document"
        )

    with col3:
        scoring_time = durations.get("scoring", 0)
        api_time = metadata.get("api_call_duration_seconds", scoring_time)
        st.metric(
            label="🧠 AI Scoring",
            value=format_duration(scoring_time),
            delta=f"API: {format_duration(api_time)}" if api_time != scoring_time else None,
            help="Time for AI reasoning and scoring"
        )

    with col4:
        total_time = durations.get("total", 0)
        st.metric(
            label="⏱️ Total Time",
            value=format_duration(total_time),
            delta=f"-{format_duration(time_saved)} saved" if time_saved > 1 else None,
            delta_color="inverse",
            help="Total evaluation pipeline duration"
        )

    # Show parallel processing info
    if time_saved > 1:
        st.success(f"⚡ **Parallel Processing:** Documents processed simultaneously in {format_duration(docs_parallel_total)} (saved {format_duration(time_saved)})")

    # Additional metadata details
    if metadata:
        with st.expander("🔍 Detailed Timing & Model Info", expanded=False):
            detail_col1, detail_col2 = st.columns(2)
            with detail_col1:
                st.markdown(f"""
                **Evaluation Details:**
                - Timestamp: `{metadata.get('evaluation_timestamp', 'N/A')}`
                - Model: `{metadata.get('model_deployment', 'N/A')}`
                - Analysis Depth: `{metadata.get('reasoning_effort', 'N/A')}`
                """)
            with detail_col2:
                api_duration = metadata.get('api_call_duration_seconds', 0)
                parse_duration = metadata.get('parse_duration_seconds', 0)
                total_eval_duration = metadata.get('total_duration_seconds', 0)
                st.markdown(f"""
                **Duration Breakdown:**
                - API Call: `{format_duration(api_duration)}`
                - Response Parsing: `{format_duration(parse_duration)}`
                - Total Evaluation: `{format_duration(total_eval_duration)}`
                """)

    st.markdown("---")


def render_score_summary(results: dict):
    """Render a visual score summary header."""
    requirement_score = results.get("requirement_score", 0)
    composite_score = results.get("composite_score", 0)
    supplier_name = results.get("supplier_name", "Unknown Vendor")

    # Determine recommendation based on composite score
    if composite_score >= 60:
        recommendation = "✅ STRONGLY RECOMMENDED"
        color = "green"
    elif composite_score >= 50:
        recommendation = "✅ RECOMMENDED"
        color = "green"
    elif composite_score >= 40:
        recommendation = "⚠️ REVIEW REQUIRED"
        color = "orange"
    else:
        recommendation = "❌ NOT RECOMMENDED"
        color = "red"

    # Display score cards
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="Supplier",
            value=supplier_name[:20] + "..." if len(supplier_name) > 20 else supplier_name
        )

    with col2:
        st.metric(
            label="Requirement Score",
            value=f"{requirement_score:.2f}",
            help="Total score out of 100"
        )

    with col3:
        st.metric(
            label="Composite Score",
            value=f"{composite_score:.2f}",
            help="Weighted score out of 70"
        )

    with col4:
        st.markdown(
            f"""
            <div style="text-align: center; padding: 10px;">
                <p style="font-size: 14px; color: gray; margin: 0;">Recommendation</p>
                <p style="font-size: 16px; font-weight: bold; color: {color}; margin: 5px 0;">{recommendation}</p>
            </div>
            """,
            unsafe_allow_html=True
        )

    st.markdown("---")
