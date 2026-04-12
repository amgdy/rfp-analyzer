"""Pipeline orchestration helpers for document processing and evaluation.

These async functions are used by both main.py and the UI step modules.
"""

import os
import time
from .document_processor import DocumentProcessor, ExtractionService
from .scoring_agent import (
    ScoringAgent,
    CriteriaExtractionAgent,
    ProposalScoringAgent,
    ExtractedCriteria,
)
from .logging_config import get_logger

logger = get_logger(__name__)

# Vendor names returned by the LLM when it cannot identify the supplier
_UNKNOWN_VENDOR_NAMES = {"Unknown Vendor", "Unknown", "N/A", ""}


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


async def extract_criteria(
    rfp_content: str,
    global_criteria: str = "",
    reasoning_effort: str = "high",
    progress_callback: callable = None,
) -> tuple[dict, float]:
    """Extract evaluation criteria from the RFP document.

    Args:
        rfp_content: The RFP content in markdown
        global_criteria: Optional user-provided additional evaluation criteria
        reasoning_effort: Reasoning effort level ("low", "medium", "high")
        progress_callback: Optional callback for progress updates

    Returns:
        Tuple of (criteria_dict, duration_seconds)
    """
    start_time = time.time()
    logger.info("Starting criteria extraction (effort: %s)...", reasoning_effort)

    agent = CriteriaExtractionAgent()

    # Combine RFP content with global criteria if provided
    if global_criteria:
        enhanced_rfp = (
            f"{rfp_content}\n\n"
            f"## Additional Evaluation Criteria (User Specified)\n\n"
            f"{global_criteria}"
        )
    else:
        enhanced_rfp = rfp_content

    criteria = await agent.extract_criteria(
        enhanced_rfp,
        progress_callback=progress_callback,
        reasoning_effort=reasoning_effort,
    )

    # Convert to dict for storage in session state
    criteria_dict = {
        "rfp_title": criteria.rfp_title,
        "rfp_summary": criteria.rfp_summary,
        "total_weight": criteria.total_weight,
        "criteria": [
            {
                "criterion_id": c.criterion_id,
                "name": c.name,
                "description": c.description,
                "category": c.category,
                "weight": c.weight,
                "max_score": c.max_score,
                "evaluation_guidance": c.evaluation_guidance,
            }
            for c in criteria.criteria
        ],
        "extraction_notes": criteria.extraction_notes,
    }

    duration = time.time() - start_time
    logger.info("Criteria extraction completed in %.2fs - Found %d criteria",
                duration, len(criteria.criteria))

    return criteria_dict, duration


async def score_proposal(
    extracted_criteria_dict: dict,
    proposal_content: str,
    reasoning_effort: str = "high",
    progress_callback: callable = None,
    proposal_filename: str = "",
) -> tuple[dict, float]:
    """Score a vendor proposal against pre-extracted criteria.

    Args:
        extracted_criteria_dict: Criteria dict from extract_criteria()
        proposal_content: The vendor proposal content
        reasoning_effort: Reasoning effort level ("low", "medium", "high")
        progress_callback: Optional callback for progress updates
        proposal_filename: Original filename of the proposal (used as fallback vendor name)

    Returns:
        Tuple of (results, duration_seconds)
    """
    start_time = time.time()
    logger.info("Starting proposal scoring (effort: %s)...", reasoning_effort)

    # Reconstruct the ExtractedCriteria pydantic model from the dict
    criteria = ExtractedCriteria(**extracted_criteria_dict)

    scoring_agent = ProposalScoringAgent()

    evaluation = await scoring_agent.score_proposal(
        criteria,
        proposal_content,
        progress_callback=progress_callback,
        reasoning_effort=reasoning_effort,
    )

    # Build results dict matching the format expected by the UI
    results = {
        "rfp_title": evaluation.rfp_title,
        "supplier_name": evaluation.supplier_name,
        "supplier_site": evaluation.supplier_site,
        "response_id": evaluation.response_id,
        "evaluation_date": evaluation.evaluation_date,
        "is_qualified_proposal": evaluation.is_qualified_proposal,
        "disqualification_reason": evaluation.disqualification_reason,
        "total_score": evaluation.total_score,
        "score_percentage": evaluation.score_percentage,
        "grade": evaluation.grade,
        "recommendation": evaluation.recommendation,
        "extracted_criteria": extracted_criteria_dict,
        "criterion_scores": [
            {
                "criterion_id": cs.criterion_id,
                "criterion_name": cs.criterion_name,
                "weight": cs.weight,
                "raw_score": cs.raw_score,
                "weighted_score": cs.weighted_score,
                "evidence": cs.evidence,
                "justification": cs.justification,
                "strengths": cs.strengths,
                "gaps": cs.gaps,
            }
            for cs in evaluation.criterion_scores
        ],
        "executive_summary": evaluation.executive_summary,
        "overall_strengths": evaluation.overall_strengths,
        "overall_weaknesses": evaluation.overall_weaknesses,
        "recommendations": evaluation.recommendations,
        "risk_assessment": evaluation.risk_assessment,
        "_metadata": {
            "version": "2.0",
            "evaluation_type": "multi-agent",
            "criteria_count": len(criteria.criteria),
            "reasoning_effort": reasoning_effort,
        },
    }

    # Fall back to filename-derived vendor name when the LLM couldn't extract one
    if results.get("supplier_name", "") in _UNKNOWN_VENDOR_NAMES and proposal_filename:
        fallback_name = os.path.splitext(proposal_filename)[0]
        logger.info("Vendor name unknown — using filename as fallback: %s", fallback_name)
        results["supplier_name"] = fallback_name

    duration = time.time() - start_time
    logger.info("Proposal scoring completed in %.2fs - Score: %.2f",
                duration, evaluation.total_score)

    return results, duration


async def evaluate_proposal(
    rfp_content: str,
    proposal_content: str,
    global_criteria: str = "",
    reasoning_effort: str = "high",
    progress_callback: callable = None,
) -> tuple[dict, float]:
    """Evaluate the vendor proposal against the RFP using AI agent.

    This is a convenience function that extracts criteria and scores in one call.

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
    logger.info("Starting full proposal evaluation (effort: %s)...", reasoning_effort)

    agent = ScoringAgent()

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
