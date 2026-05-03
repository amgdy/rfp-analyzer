"""
RFP Analyzer - Streamlit Application

A comprehensive workflow for analyzing RFPs and scoring vendor proposals:
1. Upload RFP file and Vendor proposals (multiple files)
2. Extract document content using Azure AI services
3. Review AI-extracted evaluation criteria
4. AI-powered proposal scoring and multi-vendor comparison
"""

import uuid

import streamlit as st
from pathlib import Path

# Initialize centralized logging FIRST (before other imports)
from services.logging_config import setup_logging, get_logger

setup_logging()  # Uses OTEL_LOGGING_ENABLED env var (default: False)

# Initialize OpenTelemetry tracing (after logging)
from services.telemetry import setup_telemetry, _get_app_version

setup_telemetry()

from services.document_processor import ExtractionService

# Import UI modules
from ui.landing import render_landing_page
from ui.step1_upload import render_step1
from ui.step2_extract import render_step2
from ui.step3_criteria import render_step3
from ui.step4_score import render_step4
from ui.download import render_download_page
from ui.components import render_sidebar

# Get logger (logging is already configured at import time)
logger = get_logger(__name__)

# Application version (single source of truth: pyproject.toml)
APP_VERSION = _get_app_version()

# Log application startup
logger.info("RFP Analyzer v%s starting...", APP_VERSION)


def get_scoring_guide() -> str:
    """Load the scoring guide from file."""
    guide_path = Path(__file__).parent / "scoring_guide.md"
    if guide_path.exists():
        return guide_path.read_text(encoding="utf-8")
    return ""


# Page configuration
st.set_page_config(
    page_title="RFP Analyzer",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _get_or_create_session_id() -> str:
    """Get session ID from URL query params, or generate a new one.

    The session ID is persisted exclusively in the URL query string
    so that it survives page reloads and is never stored in memory alone.
    """
    params = st.query_params
    session_id = params.get("session")
    if session_id:
        return session_id
    # Generate a new session ID and persist it in the URL immediately
    new_id = uuid.uuid4().hex[:12]
    st.query_params["session"] = new_id
    return new_id


# Initialize session state
if "step" not in st.session_state:
    st.session_state.step = 0  # Start at landing page
if "rfp_file" not in st.session_state:
    st.session_state.rfp_file = None
if "proposal_files" not in st.session_state:
    st.session_state.proposal_files = []
if "rfp_content" not in st.session_state:
    st.session_state.rfp_content = None
if "proposal_contents" not in st.session_state:
    st.session_state.proposal_contents = {}
if "evaluation_results" not in st.session_state:
    st.session_state.evaluation_results = []
if "disqualified_results" not in st.session_state:
    st.session_state.disqualified_results = []
if "comparison_results" not in st.session_state:
    st.session_state.comparison_results = None
if "extracted_criteria" not in st.session_state:
    st.session_state.extracted_criteria = None
if "step_durations" not in st.session_state:
    st.session_state.step_durations = {}
if "extraction_service" not in st.session_state:
    st.session_state.extraction_service = ExtractionService.DOCUMENT_INTELLIGENCE
if "evaluation_mode" not in st.session_state:
    st.session_state.evaluation_mode = "individual"
if "global_criteria" not in st.session_state:
    st.session_state.global_criteria = ""
if "reasoning_effort" not in st.session_state:
    st.session_state.reasoning_effort = "low"
if "extraction_queue" not in st.session_state:
    st.session_state.extraction_queue = None
if "scoring_queue" not in st.session_state:
    st.session_state.scoring_queue = None
if "is_processing" not in st.session_state:
    st.session_state.is_processing = False
if "session_id" not in st.session_state:
    st.session_state.session_id = None


def main():
    """Main application entry point."""
    # Resolve session ID from URL (or generate one)
    session_id = _get_or_create_session_id()
    if st.session_state.session_id != session_id:
        st.session_state.session_id = session_id
    # Persist session ID in the URL query string
    st.query_params["session"] = session_id

    # Check if this is a download request
    if st.query_params.get("download"):
        render_download_page()
        return

    # Restore session from blob state if needed (handles page reloads)
    _restore_session_from_blob(session_id)

    render_sidebar()

    # Render current step
    if st.session_state.step == 0:
        render_landing_page()
    elif st.session_state.step == 1:
        render_step1()
    elif st.session_state.step == 2:
        render_step2()
    elif st.session_state.step == 3:
        render_step3()
    elif st.session_state.step == 4:
        render_step4()


def _restore_session_from_blob(session_id: str):
    """Restore Streamlit session state from blob-persisted state.json.

    Only restores if session state appears empty (step == 0 and no uploads),
    which indicates a fresh page load for an existing session.
    """
    # Only attempt restore if we're at the default state
    if st.session_state.step != 0:
        return
    if st.session_state.rfp_file is not None:
        return

    try:
        from services.session_state_manager import get_session_manager
        mgr = get_session_manager(session_id)
        state = mgr.load()

        # If blob state has progress, restore it
        saved_step = state.get("current_step", 0)
        if saved_step == 0:
            return

        logger.info("Restoring session %s from step %d", session_id, saved_step)

        # Restore step
        st.session_state.step = saved_step

        # Restore config
        config = state.get("config", {})
        if config.get("extraction_service"):
            try:
                st.session_state.extraction_service = ExtractionService(config["extraction_service"])
            except ValueError:
                logger.warning("Unknown extraction service in saved state: %s", config["extraction_service"])
        if config.get("reasoning_effort"):
            st.session_state.reasoning_effort = config["reasoning_effort"]
        if config.get("global_criteria"):
            st.session_state.global_criteria = config["global_criteria"]

        # Restore upload metadata
        uploads = state.get("uploads", {})
        if uploads.get("rfp"):
            st.session_state.rfp_file = {
                "name": uploads["rfp"]["name"],
                "size": uploads["rfp"].get("size", 0),
            }
        if uploads.get("proposals"):
            st.session_state.proposal_files = [
                {"name": p["name"], "size": p.get("size", 0)}
                for p in uploads["proposals"]
            ]

        # Restore criteria
        criteria = state.get("criteria", {})
        if criteria.get("completed") and criteria.get("criteria_data"):
            st.session_state.extracted_criteria = criteria["criteria_data"]

        # Restore evaluation results
        evaluation = state.get("evaluation", {})
        if evaluation.get("completed"):
            st.session_state.evaluation_results = evaluation.get("results", [])
            st.session_state.disqualified_results = evaluation.get("disqualified", [])
            st.session_state.comparison_results = evaluation.get("comparison")

        # Restore step durations
        st.session_state.step_durations = state.get("step_durations", {})

        logger.info("Session %s restored successfully (step %d)", session_id, saved_step)

    except Exception as e:
        logger.debug("Could not restore session from blob: %s", str(e))


if __name__ == "__main__":
    main()
