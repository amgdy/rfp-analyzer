"""Step 1: Upload RFP and Vendor Proposals."""

import streamlit as st

from services.blob_storage_client import get_blob_storage_client
from services.logging_config import get_logger
from ui.components import render_step_indicator

logger = get_logger(__name__)

# Maximum file size: 500 MB per file
_MAX_FILE_SIZE_BYTES = 500 * 1024 * 1024


def _upload_to_blob(session_id: str, rfp_file=None, proposal_files=None):
    """Upload files to Azure Blob Storage under the session folder."""
    try:
        client = get_blob_storage_client()

        if rfp_file is not None:
            client.upload_rfp(session_id, rfp_file.name, rfp_file.getvalue())
            logger.info("RFP uploaded to blob storage: %s", rfp_file.name)

        if proposal_files:
            for f in proposal_files:
                client.upload_proposal(session_id, f.name, f.getvalue())
            logger.info("Uploaded %d proposals to blob storage", len(proposal_files))
    except Exception as e:
        logger.error("Failed to upload files to blob storage: %s", str(e))
        st.error(f"⚠️ Failed to upload files to storage: {e}")
        raise


def render_step1():
    """Step 1: Upload RFP and Vendor Proposals."""
    render_step_indicator(current_step=1)

    st.header("Step 1: Upload Documents")
    st.markdown("Upload the RFP document and vendor proposal files to begin the analysis.")

    # Show session ID
    session_id = st.session_state.session_id
    st.caption(f"📋 Session: `{session_id}`")

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
                    # Upload to blob storage
                    _upload_to_blob(session_id, rfp_file=rfp_file)
                st.session_state.rfp_file = {
                    "name": rfp_file.name,
                    "size": rfp_file.size,
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

                # Log and upload new files
                current_names = {p.get('name') for p in st.session_state.proposal_files} if st.session_state.proposal_files else set()
                new_names = {f.name for f in valid_files}
                if current_names != new_names:
                    logger.info("Proposal files uploaded: %d files - %s",
                               len(valid_files),
                               ", ".join(f.name for f in valid_files))
                    # Upload to blob storage
                    _upload_to_blob(session_id, proposal_files=valid_files)

                st.session_state.proposal_files = [
                    {"name": f.name, "size": f.size}
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
        st.info(
            "🔒 **Protected documents are not supported.** If your PDF or DOCX is "
            "password-protected or IRM-protected, please remove the protection "
            "before uploading."
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
            use_container_width=True,
            disabled=st.session_state.is_processing
        ):
            logger.info("User proceeding to Step 2 - RFP: %s, Proposals: %d",
                       st.session_state.rfp_file['name'],
                       len(st.session_state.proposal_files))
            # Persist session state to blob
            _save_session_state(session_id)
            st.session_state.step = 2
            st.rerun()
    else:
        st.info("📌 Please upload an RFP file and at least one vendor proposal to continue.")


def _save_session_state(session_id: str):
    """Save upload state to persistent blob storage."""
    try:
        from services.session_state_manager import get_session_manager
        mgr = get_session_manager(session_id)
        mgr.load()

        rfp_meta = None
        if st.session_state.rfp_file:
            rfp_meta = {
                "name": st.session_state.rfp_file["name"],
                "size": st.session_state.rfp_file.get("size", 0),
                "blob_path": f"{session_id}/uploads/rfp/{st.session_state.rfp_file['name']}",
            }

        proposals_meta = [
            {
                "name": p["name"],
                "size": p.get("size", 0),
                "blob_path": f"{session_id}/uploads/proposals/{p['name']}",
            }
            for p in st.session_state.proposal_files
        ]

        mgr.save_upload(rfp=rfp_meta, proposals=proposals_meta)
        mgr.save_config(
            extraction_service=st.session_state.extraction_service.value
            if hasattr(st.session_state.extraction_service, 'value')
            else str(st.session_state.extraction_service),
            reasoning_effort=st.session_state.reasoning_effort,
            global_criteria=st.session_state.global_criteria,
        )
        logger.info("Saved session state after upload step")
    except Exception as e:
        logger.debug("Failed to save session state: %s", str(e))
