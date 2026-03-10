"""Pipeline orchestration helpers for document processing and evaluation.

These async functions are used by both main.py and the UI step modules.
"""

import time
from .document_processor import DocumentProcessor, ExtractionService
from .scoring_agent_v2 import ScoringAgentV2
from .logging_config import get_logger

logger = get_logger(__name__)


async def process_document(
    file_bytes: bytes,
    filename: str,
    extraction_service: ExtractionService = ExtractionService.DOCUMENT_INTELLIGENCE,
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
    progress_callback: callable = None,
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

    agent = ScoringAgentV2()

    # Combine RFP content with global criteria if provided
    if global_criteria:
        enhanced_rfp = (
            f"{rfp_content}\n\n"
            f"## Additional Evaluation Criteria (User Specified)\n\n"
            f"{global_criteria}"
        )
    else:
        enhanced_rfp = rfp_content

    results = await agent.evaluate(
        enhanced_rfp,
        proposal_content,
        reasoning_effort=reasoning_effort,
        progress_callback=progress_callback,
    )

    duration = time.time() - start_time
    logger.info("Evaluation completed in %.2fs", duration)

    return results, duration
