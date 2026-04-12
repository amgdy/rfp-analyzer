"""
RFP Scoring Agent - Multi-Agent Architecture.

This module implements a multi-agent system for RFP evaluation:
1. Criteria Extraction Agent - Extracts scoring criteria from RFP with weights
2. Proposal Scoring Agent - Scores the proposal against extracted criteria
"""

import os
import json
import time
from datetime import datetime
from typing import Callable, Optional

from agent_framework.openai import OpenAIChatClient
from agent_framework import Agent
from azure.identity import DefaultAzureCredential
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from .logging_config import get_logger
from .token_utils import (
    estimate_token_count,
    calculate_token_budget,
    fits_in_context,
    truncate_content,
    split_content_by_tokens,
)
from .utils import parse_json_response
from .retry_utils import run_with_retry

load_dotenv()

# Get logger from centralized config
logger = get_logger(__name__)


# ============================================================================
# Pydantic Models
# ============================================================================


class ScoringCriterion(BaseModel):
    """A single scoring criterion extracted from the RFP."""

    criterion_id: str = Field(description="Unique ID for the criterion (e.g., 'C-1')")
    name: str = Field(description="Name of the criterion")
    description: str = Field(
        description="Detailed description of what is being evaluated"
    )
    category: str = Field(
        description="Category (e.g., 'Technical', 'Financial', 'Experience')"
    )
    weight: float = Field(description="Weight percentage (all weights must sum to 100)")
    max_score: int = Field(default=100, description="Maximum score for this criterion")
    evaluation_guidance: str = Field(
        description="Guidance on how to evaluate this criterion"
    )


class ExtractedCriteria(BaseModel):
    """Complete set of extracted scoring criteria from an RFP."""

    rfp_title: str = Field(description="Title of the RFP")
    rfp_summary: str = Field(description="Brief summary of what the RFP is requesting")
    total_weight: float = Field(
        default=100.0, description="Total weight (should be 100)"
    )
    criteria: list[ScoringCriterion] = Field(description="List of scoring criteria")
    extraction_notes: str = Field(description="Notes about the extraction process")


class CriterionScore(BaseModel):
    """Score for a single criterion."""

    criterion_id: str = Field(description="ID of the criterion being scored")
    criterion_name: str = Field(description="Name of the criterion")
    weight: float = Field(description="Weight percentage")
    raw_score: float = Field(description="Raw score (0-100)")
    weighted_score: float = Field(
        description="Weighted score (raw_score * weight / 100)"
    )
    evidence: str = Field(
        description="Evidence from the proposal supporting this score"
    )
    justification: str = Field(description="Detailed justification for the score")
    strengths: list[str] = Field(description="Specific strengths for this criterion")
    gaps: list[str] = Field(
        description="Specific gaps or weaknesses for this criterion"
    )


class ProposalEvaluation(BaseModel):
    """Complete evaluation result."""

    # Header Information
    rfp_title: str = Field(description="Title of the RFP")
    supplier_name: str = Field(description="Name of the vendor/supplier")
    supplier_site: str = Field(description="Location/site of the supplier")
    response_id: str = Field(description="Response/proposal ID")
    evaluation_date: str = Field(description="Date of evaluation")

    # Scoring Summary
    total_score: float = Field(description="Total weighted score (0-100)")
    score_percentage: float = Field(description="Score as percentage")
    grade: str = Field(description="Letter grade (A, B, C, D, F)")
    recommendation: str = Field(description="Overall recommendation")

    # Detailed Scores
    criterion_scores: list[CriterionScore] = Field(
        description="Scores for each criterion"
    )

    # Analysis
    executive_summary: str = Field(description="Executive summary of the evaluation")
    overall_strengths: list[str] = Field(
        description="Key strengths across all criteria"
    )
    overall_weaknesses: list[str] = Field(
        description="Key weaknesses across all criteria"
    )
    recommendations: list[str] = Field(description="Actionable recommendations")
    risk_assessment: str = Field(description="Assessment of risks with this vendor")


# ============================================================================
# Agent 1: Criteria Extraction Agent
# ============================================================================


class CriteriaExtractionAgent:
    """
    Agent responsible for extracting scoring criteria from an RFP document.

    Analyzes the RFP to identify evaluation criteria, assigns weights,
    and provides guidance for scoring each criterion.
    """

    SYSTEM_INSTRUCTIONS = """You are an expert procurement analyst specializing in RFP (Request for Proposal) analysis.

Your task is to carefully analyze RFP documents and extract comprehensive scoring criteria that will be used to evaluate vendor proposals.

## YOUR RESPONSIBILITIES:

1. **Identify Evaluation Criteria**: Find all evaluation criteria mentioned in the RFP, including:
   - Explicitly stated criteria (often in "Evaluation Criteria" or "Selection Criteria" sections)
   - Implied criteria based on requirements and priorities
   - Industry-standard criteria relevant to the type of work

2. **Assign Weights**: Distribute 100 total weight points across criteria based on:
   - Explicit weights mentioned in the RFP
   - Emphasis and priority indicated in the document
   - Industry standards for similar projects
   - Balanced evaluation across technical, financial, and qualitative factors

3. **Provide Evaluation Guidance**: For each criterion, explain:
   - What constitutes excellent performance (90-100 score)
   - What constitutes good performance (70-89 score)
   - What constitutes acceptable performance (50-69 score)
   - What constitutes poor performance (below 50)

## WEIGHT DISTRIBUTION GUIDELINES:

- Technical capabilities: typically 30-50%
- Experience and track record: typically 15-25%
- Methodology and approach: typically 15-25%
- Pricing/value: typically 15-30% (if mentioned)
- Team qualifications: typically 10-20%

## OUTPUT REQUIREMENTS:

You MUST respond with a valid JSON object matching this exact structure:

```json
{
  "rfp_title": "Extracted RFP title",
  "rfp_summary": "2-3 sentence summary of what the RFP is requesting",
  "total_weight": 100.0,
  "criteria": [
    {
      "criterion_id": "C-1",
      "name": "Criterion Name",
      "description": "Detailed description of what this criterion evaluates",
      "category": "Technical|Financial|Experience|Qualitative",
      "weight": <percentage weight>,
      "max_score": 100,
      "evaluation_guidance": "Detailed guidance on how to score this criterion"
    }
  ],
  "extraction_notes": "Notes about how criteria were identified and weighted"
}
```

## IMPORTANT:
- All weights MUST sum to exactly 100
- Include at least 4-8 meaningful criteria
- Be specific in descriptions and guidance
- Respond with ONLY valid JSON, no additional text"""

    def __init__(self):
        """Initialize the criteria extraction agent."""
        logger.info("Initializing CriteriaExtractionAgent...")

        self._validate_config()

        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")

        self.client = OpenAIChatClient(
            credential=DefaultAzureCredential(),
            azure_endpoint=endpoint,
            model=deployment_name,
            api_version="v1",
        )

        self.deployment_name = deployment_name
        logger.info("CriteriaExtractionAgent initialized")

    def _validate_config(self):
        """Validate required configuration."""
        required_vars = ["AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_DEPLOYMENT_NAME"]
        missing = [var for var in required_vars if not os.getenv(var)]
        if missing:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing)}"
            )

    async def extract_criteria(
        self,
        rfp_content: str,
        progress_callback: Optional[Callable[[str], None]] = None,
        reasoning_effort: str = "high",
    ) -> ExtractedCriteria:
        """
        Extract scoring criteria from the RFP document.

        For large RFP documents that exceed the model context window,
        automatically splits content into chunks, extracts criteria from
        each chunk, and merges the results.

        Args:
            rfp_content: The RFP document content in markdown
            progress_callback: Optional callback for progress updates
            reasoning_effort: Reasoning effort level ("low", "medium", "high")

        Returns:
            ExtractedCriteria object with all identified criteria
        """
        start_time = time.time()
        rfp_tokens = estimate_token_count(rfp_content)
        logger.info(
            "Starting criteria extraction (effort: %s, content: ~%d tokens)...",
            reasoning_effort,
            rfp_tokens,
        )

        if progress_callback:
            progress_callback("Analyzing RFP structure and requirements...")

        # Calculate available budget for user content
        budget = calculate_token_budget(self.SYSTEM_INSTRUCTIONS)
        # Reserve tokens for the prompt template text around the RFP content
        prompt_overhead = estimate_token_count(
            "Please analyze the following RFP document and extract comprehensive "
            "scoring criteria.\n\n## RFP DOCUMENT:\n\n---\n\nREQUIREMENTS:\n"
            "1. Identify all evaluation criteria\n2. Assign weights\n"
            "3. Provide guidance\n4. Include title and summary\n"
            "Respond with ONLY valid JSON matching the schema."
        )
        content_budget = budget - prompt_overhead

        if rfp_tokens <= content_budget:
            # Content fits in a single call
            logger.info(
                "RFP content (~%d tokens) fits within budget (%d tokens) — single-call extraction",
                rfp_tokens,
                content_budget,
            )
            return await self._extract_criteria_single(
                rfp_content, progress_callback, reasoning_effort, start_time
            )
        else:
            # Content too large — use chunked extraction with merge
            logger.warning(
                "RFP content (~%d tokens) exceeds budget (%d tokens) — using chunked extraction",
                rfp_tokens,
                content_budget,
            )
            return await self._extract_criteria_chunked(
                rfp_content, content_budget, progress_callback, reasoning_effort, start_time
            )

    async def _extract_criteria_single(
        self,
        rfp_content: str,
        progress_callback: Optional[Callable[[str], None]],
        reasoning_effort: str,
        start_time: float,
    ) -> ExtractedCriteria:
        """Extract criteria from RFP content in a single LLM call."""
        user_prompt = f"""Please analyze the following RFP document and extract comprehensive scoring criteria.

## RFP DOCUMENT:

{rfp_content}

---

REQUIREMENTS:
1. Identify all evaluation criteria (explicit and implied)
2. Assign weights that sum to exactly 100
3. Provide detailed evaluation guidance for each criterion
4. Include the RFP title and a brief summary

Respond with ONLY valid JSON matching the schema in your instructions."""

        try:
            agent = Agent(
                client=self.client,
                instructions=self.SYSTEM_INSTRUCTIONS,
                name="Criteria Extraction Agent",
                default_options={
                    "reasoning": {"effort": reasoning_effort, "summary": "detailed"}
                },
            )

            if progress_callback:
                progress_callback("Extracting and analyzing criteria...")

            # Lambda ensures a fresh coroutine is created on each retry attempt
            result = await run_with_retry(
                lambda: agent.run(user_prompt),
                description="Criteria extraction",
            )
            response_text = result.text

            # Log token usage
            usage = result.usage_details
            if usage:
                input_tokens = getattr(usage, "input_token_count", 0) or 0
                output_tokens = getattr(usage, "output_token_count", 0) or 0
                total_tokens = getattr(usage, "total_token_count", 0) or 0
                logger.info(
                    "Criteria extraction - Tokens: Input=%d, Output=%d, Total=%d",
                    input_tokens,
                    output_tokens,
                    total_tokens,
                )

            # Parse the response
            criteria_data = self._parse_response(response_text)

            duration = time.time() - start_time
            logger.info(
                "Criteria extraction completed in %.2fs - Found %d criteria",
                duration,
                len(criteria_data.get("criteria", [])),
            )

            return ExtractedCriteria(**criteria_data)

        except Exception as e:
            logger.error("Criteria extraction failed: %s", str(e))
            raise

    async def _extract_criteria_chunked(
        self,
        rfp_content: str,
        content_budget: int,
        progress_callback: Optional[Callable[[str], None]],
        reasoning_effort: str,
        start_time: float,
    ) -> ExtractedCriteria:
        """Extract criteria from chunked RFP content and merge results.

        Splits the RFP into chunks, extracts criteria from each, then
        deduplicates and normalizes the combined criteria.
        """
        chunks = split_content_by_tokens(rfp_content, content_budget)
        logger.info("Split RFP into %d chunks for criteria extraction", len(chunks))

        all_criteria_data: list[dict] = []
        rfp_title = ""
        rfp_summary = ""

        for i, chunk in enumerate(chunks):
            if progress_callback:
                progress_callback(
                    f"Extracting criteria from chunk {i + 1}/{len(chunks)}..."
                )

            chunk_prompt = f"""Please analyze the following section (part {i + 1} of {len(chunks)}) of an RFP document and extract scoring criteria found in this section.

## RFP DOCUMENT (Section {i + 1}/{len(chunks)}):

{chunk}

---

REQUIREMENTS:
1. Identify all evaluation criteria (explicit and implied) in this section
2. Assign preliminary weights (they will be normalized later)
3. Provide detailed evaluation guidance for each criterion
4. Include the RFP title and a brief summary if found in this section

Respond with ONLY valid JSON matching the schema in your instructions."""

            try:
                agent = Agent(
                    client=self.client,
                    instructions=self.SYSTEM_INSTRUCTIONS,
                    name=f"Criteria Extraction Agent (chunk {i + 1})",
                    default_options={
                        "reasoning": {"effort": reasoning_effort, "summary": "detailed"}
                    },
                )

                result = await run_with_retry(
                    lambda: agent.run(chunk_prompt),
                    description=f"Criteria extraction (chunk {i + 1}/{len(chunks)})",
                )
                chunk_data = self._parse_response(result.text)
                all_criteria_data.append(chunk_data)

                # Capture title/summary from first chunk that has them
                if not rfp_title and chunk_data.get("rfp_title", "Unknown RFP") != "Unknown RFP":
                    rfp_title = chunk_data["rfp_title"]
                if not rfp_summary and chunk_data.get("rfp_summary"):
                    rfp_summary = chunk_data["rfp_summary"]

                logger.info(
                    "Chunk %d/%d: extracted %d criteria",
                    i + 1,
                    len(chunks),
                    len(chunk_data.get("criteria", [])),
                )

            except Exception as e:
                logger.error("Criteria extraction failed for chunk %d: %s", i + 1, str(e))
                # Continue with other chunks

        # Merge criteria from all chunks
        merged = self._merge_chunked_criteria(all_criteria_data, rfp_title, rfp_summary)

        duration = time.time() - start_time
        logger.info(
            "Chunked criteria extraction completed in %.2fs - Merged %d criteria from %d chunks",
            duration,
            len(merged.get("criteria", [])),
            len(chunks),
        )

        return ExtractedCriteria(**merged)

    def _merge_chunked_criteria(
        self,
        all_data: list[dict],
        rfp_title: str,
        rfp_summary: str,
    ) -> dict:
        """Merge criteria extracted from multiple chunks.

        Deduplicates by criterion name (case-insensitive) and normalizes
        weights to sum to 100.
        """
        seen_names: dict[str, dict] = {}

        for chunk_data in all_data:
            for criterion in chunk_data.get("criteria", []):
                name_key = criterion.get("name", "").lower().strip()
                if name_key and name_key not in seen_names:
                    seen_names[name_key] = criterion

        criteria_list = list(seen_names.values())

        # Re-assign criterion IDs
        for i, c in enumerate(criteria_list, 1):
            c["criterion_id"] = f"C-{i}"

        # Normalize weights to sum to 100
        total_weight = sum(c.get("weight", 0) for c in criteria_list)
        if criteria_list and total_weight > 0 and abs(total_weight - 100) > 0.1:
            for c in criteria_list:
                c["weight"] = (c.get("weight", 0) / total_weight) * 100

        return {
            "rfp_title": rfp_title or "Unknown RFP",
            "rfp_summary": rfp_summary or "Large RFP document (processed in chunks)",
            "total_weight": 100.0,
            "criteria": criteria_list,
            "extraction_notes": f"Extracted from {len(all_data)} document chunks, "
            f"merged {len(criteria_list)} unique criteria",
        }

    def _parse_response(self, response_text: str) -> dict:
        """Parse the agent response into a dictionary."""
        try:
            data = parse_json_response(response_text)

            # Validate and normalize weights
            criteria = data.get("criteria", [])
            total_weight = sum(c.get("weight", 0) for c in criteria)

            # Normalize if weights don't sum to 100
            if criteria and abs(total_weight - 100) > 0.1:
                logger.warning("Normalizing weights from %.2f to 100", total_weight)
                for criterion in criteria:
                    criterion["weight"] = (
                        criterion.get("weight", 0) / total_weight
                    ) * 100
                data["total_weight"] = 100.0

            return data

        except json.JSONDecodeError as e:
            logger.error("Failed to parse criteria JSON: %s", str(e))
            # Return default structure
            return {
                "rfp_title": "Unknown RFP",
                "rfp_summary": "Failed to extract RFP summary",
                "total_weight": 100.0,
                "criteria": [],
                "extraction_notes": f"Error parsing response: {str(e)}",
            }


# ============================================================================
# Agent 2: Proposal Scoring Agent
# ============================================================================


class ProposalScoringAgent:
    """
    Agent responsible for scoring a proposal against extracted criteria.

    Takes the criteria from Agent 1 and evaluates the vendor proposal,
    providing detailed scores and justifications.
    """

    SYSTEM_INSTRUCTIONS_TEMPLATE = """You are an expert procurement evaluator with extensive experience scoring vendor proposals.

Your task is to objectively evaluate a vendor proposal against specific scoring criteria extracted from an RFP.

## SCORING METHODOLOGY:

For EACH criterion, you must:

1. **Find Evidence**: Locate relevant content in the proposal
2. **Assess Quality**: Compare against the evaluation guidance
3. **Assign Score**: Score 0-100 based on:
   - 90-100 (Excellent): Exceeds requirements, exceptional quality
   - 70-89 (Good): Fully meets requirements, high quality
   - 50-69 (Acceptable): Meets minimum requirements
   - 30-49 (Below Average): Partially meets requirements
   - 0-29 (Poor): Fails to meet requirements

4. **Calculate Weighted Score**: weighted_score = (raw_score * weight) / 100

5. **Document Everything**: Provide evidence, justification, strengths, and gaps

## EVALUATION CRITERIA TO USE:

{criteria_json}

## GRADE ASSIGNMENT:

Based on total weighted score:
- A: 90-100
- B: 80-89
- C: 70-79
- D: 60-69
- F: Below 60

## OUTPUT FORMAT:

You MUST respond with a valid JSON object:

```json
{{
  "rfp_title": "RFP title",
  "supplier_name": "Extracted vendor name",
  "supplier_site": "Vendor location",
  "response_id": "Generate ID like RESP-2025-XXXX",
  "evaluation_date": "YYYY-MM-DD",
  "total_score": <sum of all weighted scores>,
  "score_percentage": <total_score as percentage>,
  "grade": "A/B/C/D/F",
  "recommendation": "Clear recommendation statement",
  "criterion_scores": [
    {{
      "criterion_id": "C-1",
      "criterion_name": "Criterion Name",
      "weight": <weight>,
      "raw_score": <0-100>,
      "weighted_score": <calculated>,
      "evidence": "Specific evidence from proposal",
      "justification": "Detailed scoring justification",
      "strengths": ["strength1", "strength2"],
      "gaps": ["gap1", "gap2"]
    }}
  ],
  "executive_summary": "2-3 paragraph executive summary",
  "overall_strengths": ["key strength 1", "key strength 2"],
  "overall_weaknesses": ["key weakness 1", "key weakness 2"],
  "recommendations": ["recommendation 1", "recommendation 2"],
  "risk_assessment": "Assessment of risks with this vendor"
}}
```

## IMPORTANT:
- Score EVERY criterion from the provided list
- Provide specific evidence from the proposal
- Be objective and fair
- Respond with ONLY valid JSON"""

    def __init__(self):
        """Initialize the proposal scoring agent."""
        logger.info("Initializing ProposalScoringAgent...")

        self._validate_config()

        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")

        self.client = OpenAIChatClient(
            credential=DefaultAzureCredential(),
            azure_endpoint=endpoint,
            model=deployment_name,
            api_version="v1",
        )

        self.deployment_name = deployment_name
        logger.info("ProposalScoringAgent initialized")

    def _validate_config(self):
        """Validate required configuration."""
        required_vars = ["AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_DEPLOYMENT_NAME"]
        missing = [var for var in required_vars if not os.getenv(var)]
        if missing:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing)}"
            )

    async def score_proposal(
        self,
        criteria: ExtractedCriteria,
        proposal_content: str,
        progress_callback: Optional[Callable[[str], None]] = None,
        reasoning_effort: str = "high",
    ) -> ProposalEvaluation:
        """
        Score the proposal against extracted criteria.

        For large proposals that exceed the model context window,
        automatically splits content into chunks, scores each chunk,
        and merges scores by taking the best evidence per criterion.

        Args:
            criteria: ExtractedCriteria from the extraction agent
            proposal_content: The vendor proposal content
            progress_callback: Optional callback for progress updates
            reasoning_effort: Reasoning effort level ("low", "medium", "high")

        Returns:
            ProposalEvaluation with complete scoring results
        """
        start_time = time.time()
        proposal_tokens = estimate_token_count(proposal_content)
        logger.info(
            "Starting proposal scoring against %d criteria (effort: %s, proposal: ~%d tokens)...",
            len(criteria.criteria),
            reasoning_effort,
            proposal_tokens,
        )

        if progress_callback:
            progress_callback("Preparing scoring framework...")

        # Format criteria for the system instructions
        criteria_json = json.dumps(
            [
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
            indent=2,
        )

        system_instructions = self.SYSTEM_INSTRUCTIONS_TEMPLATE.format(
            criteria_json=criteria_json
        )

        # Calculate available budget for proposal content
        budget = calculate_token_budget(system_instructions)
        # Reserve tokens for the prompt template text around the proposal
        prompt_overhead = estimate_token_count(
            f"Please evaluate the following vendor proposal against the scoring criteria.\n\n"
            f"## RFP CONTEXT:\n- Title: {criteria.rfp_title}\n- Summary: {criteria.rfp_summary}\n\n"
            f"## VENDOR PROPOSAL:\n\n---\n\nREQUIREMENTS:\n1-5...\nRespond with ONLY valid JSON."
        )
        content_budget = budget - prompt_overhead

        if proposal_tokens <= content_budget:
            logger.info(
                "Proposal (~%d tokens) fits within budget (%d tokens) — single-call scoring",
                proposal_tokens,
                content_budget,
            )
            return await self._score_proposal_single(
                criteria, criteria_json, system_instructions, proposal_content,
                progress_callback, reasoning_effort, start_time,
            )
        else:
            logger.warning(
                "Proposal (~%d tokens) exceeds budget (%d tokens) — using chunked scoring",
                proposal_tokens,
                content_budget,
            )
            return await self._score_proposal_chunked(
                criteria, criteria_json, system_instructions, proposal_content,
                content_budget, progress_callback, reasoning_effort, start_time,
            )

    async def _score_proposal_single(
        self,
        criteria: ExtractedCriteria,
        criteria_json: str,
        system_instructions: str,
        proposal_content: str,
        progress_callback: Optional[Callable[[str], None]],
        reasoning_effort: str,
        start_time: float,
    ) -> ProposalEvaluation:
        """Score proposal content in a single LLM call."""
        user_prompt = f"""Please evaluate the following vendor proposal against the scoring criteria.

## RFP CONTEXT:
- Title: {criteria.rfp_title}
- Summary: {criteria.rfp_summary}

## VENDOR PROPOSAL:

{proposal_content}

---

REQUIREMENTS:
1. Score each criterion from 0-100
2. Calculate weighted scores
3. Provide evidence and justification for each score
4. Summarize strengths, weaknesses, and recommendations
5. Assign an overall grade

Respond with ONLY valid JSON matching the schema in your instructions."""

        try:
            agent = Agent(
                client=self.client,
                instructions=system_instructions,
                name="Proposal Scoring Agent",
                default_options={
                    "reasoning": {"effort": reasoning_effort, "summary": "detailed"}
                },
            )

            if progress_callback:
                progress_callback("Scoring proposal against criteria...")

            result = await run_with_retry(
                lambda: agent.run(user_prompt),
                description="Proposal scoring",
            )
            response_text = result.text

            # Log token usage
            usage = result.usage_details
            if usage:
                input_tokens = getattr(usage, "input_token_count", 0) or 0
                output_tokens = getattr(usage, "output_token_count", 0) or 0
                total_tokens = getattr(usage, "total_token_count", 0) or 0
                logger.info(
                    "Proposal scoring - Tokens: Input=%d, Output=%d, Total=%d",
                    input_tokens,
                    output_tokens,
                    total_tokens,
                )

            # Parse the response
            evaluation_data = self._parse_response(response_text, criteria)

            duration = time.time() - start_time
            logger.info(
                "Proposal scoring completed in %.2fs - Total score: %.2f",
                duration,
                evaluation_data.get("total_score", 0),
            )

            return ProposalEvaluation(**evaluation_data)

        except Exception as e:
            logger.error("Proposal scoring failed: %s", str(e))
            raise

    async def _score_proposal_chunked(
        self,
        criteria: ExtractedCriteria,
        criteria_json: str,
        system_instructions: str,
        proposal_content: str,
        content_budget: int,
        progress_callback: Optional[Callable[[str], None]],
        reasoning_effort: str,
        start_time: float,
    ) -> ProposalEvaluation:
        """Score a large proposal by processing chunks and merging results.

        For each criterion, the highest score across all chunks is kept
        (since different parts of the proposal may address different criteria).
        """
        chunks = split_content_by_tokens(proposal_content, content_budget)
        logger.info("Split proposal into %d chunks for scoring", len(chunks))

        chunk_evaluations: list[dict] = []

        for i, chunk in enumerate(chunks):
            if progress_callback:
                progress_callback(
                    f"Scoring proposal chunk {i + 1}/{len(chunks)}..."
                )

            chunk_prompt = f"""Please evaluate the following SECTION (part {i + 1} of {len(chunks)}) of a vendor proposal against the scoring criteria.

NOTE: This is a partial document. Score criteria based ONLY on evidence found in this section.
If a criterion is not addressed in this section, assign a score of 0 for that criterion.

## RFP CONTEXT:
- Title: {criteria.rfp_title}
- Summary: {criteria.rfp_summary}

## VENDOR PROPOSAL (Section {i + 1}/{len(chunks)}):

{chunk}

---

REQUIREMENTS:
1. Score each criterion from 0-100 based on evidence in THIS section only
2. Calculate weighted scores
3. Provide evidence and justification for each score
4. Assign score 0 for criteria not addressed in this section
5. Assign an overall grade

Respond with ONLY valid JSON matching the schema in your instructions."""

            try:
                agent = Agent(
                    client=self.client,
                    instructions=system_instructions,
                    name=f"Proposal Scoring Agent (chunk {i + 1})",
                    default_options={
                        "reasoning": {"effort": reasoning_effort, "summary": "detailed"}
                    },
                )

                result = await run_with_retry(
                    lambda: agent.run(chunk_prompt),
                    description=f"Proposal scoring (chunk {i + 1}/{len(chunks)})",
                )
                chunk_data = self._parse_response(result.text, criteria)
                chunk_evaluations.append(chunk_data)

                logger.info(
                    "Chunk %d/%d scored — total: %.2f",
                    i + 1,
                    len(chunks),
                    chunk_data.get("total_score", 0),
                )

            except Exception as e:
                logger.error("Scoring failed for chunk %d: %s", i + 1, str(e))

        if not chunk_evaluations:
            raise RuntimeError("All proposal chunks failed to score")

        # Merge chunk evaluations: take best score per criterion
        merged = self._merge_chunked_scores(chunk_evaluations, criteria)

        duration = time.time() - start_time
        logger.info(
            "Chunked proposal scoring completed in %.2fs - Total score: %.2f (from %d chunks)",
            duration,
            merged.get("total_score", 0),
            len(chunks),
        )

        return ProposalEvaluation(**merged)

    def _merge_chunked_scores(
        self,
        chunk_evaluations: list[dict],
        criteria: ExtractedCriteria,
    ) -> dict:
        """Merge scores from multiple chunks by taking the best per criterion.

        For each criterion, selects the chunk that gave the highest raw_score,
        keeping its evidence, justification, strengths, and gaps.
        """
        best_scores: dict[str, dict] = {}

        for eval_data in chunk_evaluations:
            for cs in eval_data.get("criterion_scores", []):
                cid = cs.get("criterion_id", "")
                raw = cs.get("raw_score", 0) or 0
                if cid not in best_scores or raw > (best_scores[cid].get("raw_score", 0) or 0):
                    best_scores[cid] = cs

        # Recalculate weighted scores and totals
        merged_scores = list(best_scores.values())
        for cs in merged_scores:
            weight = cs.get("weight", 0)
            raw = cs.get("raw_score", 0)
            cs["weighted_score"] = round((raw * weight) / 100, 2)

        total_score = round(sum(cs.get("weighted_score", 0) for cs in merged_scores), 2)

        # Determine grade
        if total_score >= 90:
            grade = "A"
        elif total_score >= 80:
            grade = "B"
        elif total_score >= 70:
            grade = "C"
        elif total_score >= 60:
            grade = "D"
        else:
            grade = "F"

        # Use first evaluation for non-score fields, prefer non-empty values
        base = chunk_evaluations[0]
        for eval_data in chunk_evaluations[1:]:
            for field in ["supplier_name", "supplier_site", "executive_summary", "recommendation"]:
                if not base.get(field) and eval_data.get(field):
                    base[field] = eval_data[field]

        # Merge list fields from all chunks
        all_strengths = []
        all_weaknesses = []
        all_recommendations = []
        for eval_data in chunk_evaluations:
            all_strengths.extend(eval_data.get("overall_strengths", []))
            all_weaknesses.extend(eval_data.get("overall_weaknesses", []))
            all_recommendations.extend(eval_data.get("recommendations", []))

        return {
            "rfp_title": base.get("rfp_title", criteria.rfp_title),
            "supplier_name": base.get("supplier_name", "Unknown Vendor"),
            "supplier_site": base.get("supplier_site", "Unknown"),
            "response_id": base.get("response_id", "RESP-CHUNKED"),
            "evaluation_date": base.get("evaluation_date", ""),
            "total_score": total_score,
            "score_percentage": total_score,
            "grade": grade,
            "recommendation": base.get("recommendation", ""),
            "criterion_scores": merged_scores,
            "executive_summary": base.get("executive_summary", "Evaluation based on chunked analysis"),
            "overall_strengths": list(dict.fromkeys(all_strengths)),  # deduplicate preserving order
            "overall_weaknesses": list(dict.fromkeys(all_weaknesses)),
            "recommendations": list(dict.fromkeys(all_recommendations)),
            "risk_assessment": base.get("risk_assessment", ""),
        }

    def _parse_response(self, response_text: str, criteria: ExtractedCriteria) -> dict:
        """Parse the agent response into a dictionary."""
        try:
            data = parse_json_response(response_text)

            # Ensure evaluation_date is set
            if not data.get("evaluation_date"):
                data["evaluation_date"] = datetime.now().strftime("%Y-%m-%d")

            # Recalculate total score for accuracy
            criterion_scores = data.get("criterion_scores", [])
            total_score = sum(cs.get("weighted_score", 0) for cs in criterion_scores)
            data["total_score"] = round(total_score, 2)
            data["score_percentage"] = round(total_score, 2)

            # Determine grade
            if total_score >= 90:
                data["grade"] = "A"
            elif total_score >= 80:
                data["grade"] = "B"
            elif total_score >= 70:
                data["grade"] = "C"
            elif total_score >= 60:
                data["grade"] = "D"
            else:
                data["grade"] = "F"

            return data

        except json.JSONDecodeError as e:
            logger.error("Failed to parse scoring JSON: %s", str(e))
            # Return default structure
            return {
                "rfp_title": criteria.rfp_title,
                "supplier_name": "Unknown Vendor",
                "supplier_site": "Unknown",
                "response_id": "RESP-ERROR",
                "evaluation_date": datetime.now().strftime("%Y-%m-%d"),
                "total_score": 0,
                "score_percentage": 0,
                "grade": "F",
                "recommendation": "Unable to complete evaluation due to parsing error",
                "criterion_scores": [],
                "executive_summary": f"Error parsing evaluation: {str(e)}",
                "overall_strengths": [],
                "overall_weaknesses": [],
                "recommendations": [],
                "risk_assessment": "Unable to assess",
            }


# ============================================================================
# Main Scoring Orchestrator
# ============================================================================


class ScoringAgent:
    """
    Multi-Agent RFP Scoring System.

    Orchestrates two agents:
    1. CriteriaExtractionAgent - Extracts scoring criteria from RFP
    2. ProposalScoringAgent - Scores proposal against criteria
    """

    def __init__(self):
        """Initialize the scoring system."""
        logger.info("Initializing ScoringAgent (Multi-Agent System)...")

        self.criteria_agent = CriteriaExtractionAgent()
        self.scoring_agent = ProposalScoringAgent()

        logger.info("ScoringAgent initialized with 2 agents")

    async def evaluate(
        self,
        rfp_content: str,
        proposal_content: str,
        scoring_guide: str = "",  # Kept for API compatibility but not used in v2
        progress_callback: Optional[Callable[[str], None]] = None,
        reasoning_effort: str = "high",
    ) -> dict:
        """
        Perform full multi-agent evaluation.

        Args:
            rfp_content: The RFP document content
            proposal_content: The vendor proposal content
            scoring_guide: (Unused - criteria extracted from RFP)
            progress_callback: Optional callback for progress updates
            reasoning_effort: Reasoning effort level ("low", "medium", "high")

        Returns:
            Dictionary containing complete evaluation results with metadata
        """
        total_start = time.time()
        logger.info(
            "====== MULTI-AGENT EVALUATION STARTED (effort: %s) ======",
            reasoning_effort,
        )

        # Phase 1: Extract criteria from RFP
        phase1_start = time.time()
        if progress_callback:
            progress_callback("Phase 1: Extracting scoring criteria from RFP...")

        criteria = await self.criteria_agent.extract_criteria(
            rfp_content,
            progress_callback=progress_callback,
            reasoning_effort=reasoning_effort,
        )
        phase1_duration = time.time() - phase1_start

        logger.info(
            "Phase 1 completed in %.2fs - Extracted %d criteria",
            phase1_duration,
            len(criteria.criteria),
        )

        # Phase 2: Score the proposal
        phase2_start = time.time()
        if progress_callback:
            progress_callback("Phase 2: Scoring proposal against extracted criteria...")

        evaluation = await self.scoring_agent.score_proposal(
            criteria,
            proposal_content,
            progress_callback=progress_callback,
            reasoning_effort=reasoning_effort,
        )
        phase2_duration = time.time() - phase2_start

        logger.info(
            "Phase 2 completed in %.2fs - Total score: %.2f",
            phase2_duration,
            evaluation.total_score,
        )

        # Compile final results
        total_duration = time.time() - total_start

        results = {
            # Header info (compatible with V1 format where possible)
            "rfp_title": evaluation.rfp_title,
            "supplier_name": evaluation.supplier_name,
            "supplier_site": evaluation.supplier_site,
            "response_id": evaluation.response_id,
            "evaluation_date": evaluation.evaluation_date,
            # Scoring
            "total_score": evaluation.total_score,
            "score_percentage": evaluation.score_percentage,
            "grade": evaluation.grade,
            "recommendation": evaluation.recommendation,
            # Criteria and scores
            "extracted_criteria": {
                "rfp_summary": criteria.rfp_summary,
                "total_weight": criteria.total_weight,
                "criteria_count": len(criteria.criteria),
                "criteria": [
                    {
                        "criterion_id": c.criterion_id,
                        "name": c.name,
                        "description": c.description,
                        "category": c.category,
                        "weight": c.weight,
                        "evaluation_guidance": c.evaluation_guidance,
                    }
                    for c in criteria.criteria
                ],
                "extraction_notes": criteria.extraction_notes,
            },
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
            # Analysis
            "executive_summary": evaluation.executive_summary,
            "overall_strengths": evaluation.overall_strengths,
            "overall_weaknesses": evaluation.overall_weaknesses,
            "recommendations": evaluation.recommendations,
            "risk_assessment": evaluation.risk_assessment,
            # Metadata
            "_metadata": {
                "version": "2.0",
                "evaluation_type": "multi-agent",
                "evaluation_timestamp": datetime.now().isoformat(),
                "total_duration_seconds": round(total_duration, 2),
                "phase1_criteria_extraction_seconds": round(phase1_duration, 2),
                "phase2_proposal_scoring_seconds": round(phase2_duration, 2),
                "criteria_count": len(criteria.criteria),
                "model_deployment": self.criteria_agent.deployment_name,
                "reasoning_effort": reasoning_effort,
            },
        }

        logger.info("====== MULTI-AGENT EVALUATION COMPLETED ======")
        logger.info(
            "Total duration: %.2fs (Phase 1: %.2fs, Phase 2: %.2fs)",
            total_duration,
            phase1_duration,
            phase2_duration,
        )

        return results
