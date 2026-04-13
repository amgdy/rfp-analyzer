"""Step 1: Upload RFP and Vendor Proposals."""

import streamlit as st

from services.logging_config import get_logger
from ui.components import render_step_indicator

logger = get_logger(__name__)

# Maximum file size: 500 MB per file
_MAX_FILE_SIZE_BYTES = 500 * 1024 * 1024


def render_step1():
    """Step 1: Upload RFP and Vendor Proposals."""
    render_step_indicator(current_step=1)

    st.header("Step 1: Upload Documents")
    st.markdown("Upload the RFP document and vendor proposal files to begin the analysis.")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📄 RFP Document")
        st.markdown("Upload a single RFP file")

        rfp_file = st.file_uploader(
            "Choose RFP file",
            type=["pdf", "docx", "txt", "md"],
            key="rfp_uploader",
            help="PDF & DOCX → extracted via AI  |  TXT & MD → read directly (instant)"
        )

        if rfp_file is not None:
            if rfp_file.size > _MAX_FILE_SIZE_BYTES:
                st.error(f"⚠️ File **{rfp_file.name}** exceeds the 500 MB size limit.")
            else:
                st.info(f"📎 **{rfp_file.name}** ({rfp_file.size / 1024:.1f} KB)")
                if st.session_state.rfp_file is None or st.session_state.rfp_file.get('name') != rfp_file.name:
                    logger.info("RFP file uploaded: %s (%.1f KB)", rfp_file.name, rfp_file.size / 1024)
                st.session_state.rfp_file = {
                    "bytes": rfp_file.getvalue(),
                    "name": rfp_file.name
                }

            if st.session_state.rfp_file:
            st.success(f"✅ RFP ready: {st.session_state.rfp_file['name']}")

    with col2:
        st.subheader("📝 Vendor Proposals")
        st.markdown("Upload one or more vendor proposal files")

        proposal_files = st.file_uploader(
            "Choose Vendor Proposal files",
            type=["pdf", "docx", "txt", "md"],
            key="proposals_uploader",
            accept_multiple_files=True,
            help="PDF & DOCX → extracted via AI  |  TXT & MD → read directly (instant)"
        )

        if proposal_files:
            oversized = [f for f in proposal_files if f.size > _MAX_FILE_SIZE_BYTES]
            if oversized:
                for f in oversized:
                    st.error(f"⚠️ File **{f.name}** exceeds the 500 MB size limit.")
            valid_files = [f for f in proposal_files if f.size <= _MAX_FILE_SIZE_BYTES]

            if valid_files:
                st.info(f"📎 {len(valid_files)} file(s) selected")
                for f in valid_files:
                    st.caption(f"• {f.name} ({f.size / 1024:.1f} KB)")

                # Log new uploads
                current_names = {p.get('name') for p in st.session_state.proposal_files} if st.session_state.proposal_files else set()
                new_names = {f.name for f in valid_files}
                if current_names != new_names:
                    logger.info("Proposal files uploaded: %d files - %s",
                               len(valid_files),
                               ", ".join(f.name for f in valid_files))

                st.session_state.proposal_files = [
                    {"bytes": f.getvalue(), "name": f.name}
                    for f in valid_files
                ]

        if st.session_state.proposal_files:
            st.success(f"✅ {len(st.session_state.proposal_files)} proposal(s) ready")

    # File type processing info
    with st.expander("ℹ️ How different file formats are processed", expanded=False):
        st.markdown(
            "| Format | Processing | Speed |\n"
            "|--------|-----------|-------|\n"
            "| **PDF** | AI extraction (Content Understanding / Document Intelligence) | ~10-30s |\n"
            "| **DOCX** | AI extraction or local conversion | ~5-20s |\n"
            "| **TXT** | Read directly — no extraction needed | Instant |\n"
            "| **MD** | Read directly — no extraction needed | Instant |"
        )

    st.markdown("---")

    # Global Evaluation Criteria
    st.subheader("📋 Global Evaluation Criteria (Optional)")
    st.markdown("Add additional evaluation criteria that will be used alongside criteria extracted from the RFP.")

    global_criteria = st.text_area(
        "Enter additional evaluation criteria:",
        value=st.session_state.global_criteria,
        height=150,
        placeholder="Example:\n- Cost effectiveness: 20%\n- Sustainability practices: 15%\n- Local presence: 10%",
        help="These criteria will be added to the automatically extracted criteria from the RFP."
    )
    st.session_state.global_criteria = global_criteria

    st.markdown("---")

    # Proceed button
    can_proceed = st.session_state.rfp_file is not None and len(st.session_state.proposal_files) > 0

    if can_proceed:
        if st.button(
            "Continue to Step 2: Extract Content →",
            type="primary",
            width="stretch",
            disabled=st.session_state.is_processing
        ):
            logger.info("User proceeding to Step 2 - RFP: %s, Proposals: %d",
                       st.session_state.rfp_file['name'],
                       len(st.session_state.proposal_files))
            st.session_state.step = 2
            st.rerun()
    else:
        st.info("📌 Please upload an RFP file and at least one vendor proposal to continue.")
