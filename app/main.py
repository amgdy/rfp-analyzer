"""
RFP Analyzer - Streamlit Application

A comprehensive workflow for analyzing RFPs and scoring vendor proposals:
1. Upload RFP file and Vendor proposals (multiple files)
2. Configure extraction service and evaluation criteria
3. AI-powered evaluation and multi-vendor comparison
"""

import os
import streamlit as st
from pathlib import Path
import asyncio
import time
import logging

# Initialize centralized logging FIRST (before other imports)
from services.logging_config import setup_logging, get_logger
setup_logging()  # Uses OTEL_LOGGING_ENABLED env var (default: False)

from services.document_processor import DocumentProcessor, ExtractionService
from services.scoring_agent_v2 import ScoringAgentV2
from services.comparison_agent import ComparisonAgent

# Import UI modules
from ui.landing import render_landing_page
from ui.step1_upload import render_step1
from ui.step2_extract import render_step2
from ui.step3_evaluate import render_step3
from ui.components import render_sidebar

# Get logger (logging is already configured at import time)
logger = get_logger(__name__)

# Log application startup
logger.info("RFP Analyzer application starting...")


def get_scoring_guide() -> str:
    """Load the scoring guide from file."""
    guide_path = Path(__file__).parent / "scoring_guide.md"
    if guide_path.exists():
        return guide_path.read_text(encoding="utf-8")
    return ""


async def process_document(
    file_bytes: bytes,
    filename: str,
    extraction_service: ExtractionService = ExtractionService.DOCUMENT_INTELLIGENCE
) -> tuple[str, float]:
    """Process uploaded document using the configured extraction service.

    Args:
        file_bytes: Document content as bytes
        filename: Original filename
        extraction_service: Which service to use for extraction

    Returns:
        Tuple of (content, duration_seconds)
    """
    start_time = time.time()
    logger.info("Starting document processing: %s using %s", filename, extraction_service.value)

    processor = DocumentProcessor(service=extraction_service)
    content = await processor.extract_content(file_bytes, filename)

    duration = time.time() - start_time
    logger.info("Document processed: %s (%.2fs, %d chars)", filename, duration, len(content))

    return content, duration


async def evaluate_proposal(
    rfp_content: str,
    proposal_content: str,
    global_criteria: str = "",
    reasoning_effort: str = "high",
    progress_callback: callable = None
) -> tuple[dict, float]:
    """Evaluate the vendor proposal against the RFP using AI agent.

    Args:
        rfp_content: The RFP content
        proposal_content: The proposal content
        global_criteria: Optional user-provided global evaluation criteria
        reasoning_effort: Reasoning effort level ("low", "medium", "high")
        progress_callback: Optional callback for progress updates

    Returns:
        Tuple of (results, duration_seconds)
    """
    start_time = time.time()
    logger.info("Starting proposal evaluation (effort: %s)...", reasoning_effort)

    # Always use V2 (multi-agent) for evaluation
    agent = ScoringAgentV2()

    # Combine RFP content with global criteria if provided
    if global_criteria:
        enhanced_rfp = f"{rfp_content}\n\n## Additional Evaluation Criteria (User Specified)\n\n{global_criteria}"
    else:
        enhanced_rfp = rfp_content

    results = await agent.evaluate(
        enhanced_rfp,
        proposal_content,
        reasoning_effort=reasoning_effort,
        progress_callback=progress_callback
    )

    duration = time.time() - start_time
    logger.info("Evaluation completed in %.2fs", duration)

    return results, duration


# Page configuration
st.set_page_config(
    page_title="RFP Analyzer",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
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
if "comparison_results" not in st.session_state:
    st.session_state.comparison_results = None
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


if __name__ == "__main__":
    main()
