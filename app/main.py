"""
RFP Analyzer - Streamlit Application

A comprehensive workflow for analyzing RFPs and scoring vendor proposals:
1. Upload RFP file and Vendor proposals (multiple files)
2. Extract document content using Azure AI services
3. Review AI-extracted evaluation criteria
4. AI-powered proposal scoring and multi-vendor comparison
"""

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


def main():
    """Main application entry point."""
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


if __name__ == "__main__":
    main()
