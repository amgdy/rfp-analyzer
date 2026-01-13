"""
RFP Scoring Agent V2 - Multi-Agent Architecture.

This module implements a multi-agent system for RFP evaluation:
1. Criteria Extraction Agent - Extracts scoring criteria from RFP with weights
2. Proposal Scoring Agent - Scores the proposal against extracted criteria
"""

import os
import json
import logging
import time
from datetime import datetime
from typing import Callable, Optional

from agent_framework.azure import AzureOpenAIResponsesClient
from azure.identity import DefaultAzureCredential
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s.%(msecs)03d | %(levelname)s | %(name)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# ============================================================================
# Pydantic Models for V2 Scoring
# ============================================================================

class ScoringCriterion(BaseModel):
    """A single scoring criterion extracted from the RFP."""
    criterion_id: str = Field(description="Unique ID for the criterion (e.g., 'C-1')")
    name: str = Field(description="Name of the criterion")
    description: str = Field(description="Detailed description of what is being evaluated")
    category: str = Field(description="Category (e.g., 'Technical', 'Financial', 'Experience')")
    weight: float = Field(description="Weight percentage (all weights must sum to 100)")
    max_score: int = Field(default=100, description="Maximum score for this criterion")
    evaluation_guidance: str = Field(description="Guidance on how to evaluate this criterion")


class ExtractedCriteria(BaseModel):
    """Complete set of extracted scoring criteria from an RFP."""
    rfp_title: str = Field(description="Title of the RFP")
    rfp_summary: str = Field(description="Brief summary of what the RFP is requesting")
    total_weight: float = Field(default=100.0, description="Total weight (should be 100)")
    criteria: list[ScoringCriterion] = Field(description="List of scoring criteria")
    extraction_notes: str = Field(description="Notes about the extraction process")


class CriterionScore(BaseModel):
    """Score for a single criterion."""
    criterion_id: str = Field(description="ID of the criterion being scored")
    criterion_name: str = Field(description="Name of the criterion")
    weight: float = Field(description="Weight percentage")
    raw_score: float = Field(description="Raw score (0-100)")
    weighted_score: float = Field(description="Weighted score (raw_score * weight / 100)")
    evidence: str = Field(description="Evidence from the proposal supporting this score")
    justification: str = Field(description="Detailed justification for the score")
    strengths: list[str] = Field(description="Specific strengths for this criterion")
    gaps: list[str] = Field(description="Specific gaps or weaknesses for this criterion")


class ProposalEvaluationV2(BaseModel):
    """Complete V2 evaluation result."""
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
    criterion_scores: list[CriterionScore] = Field(description="Scores for each criterion")
    
    # Analysis
    executive_summary: str = Field(description="Executive summary of the evaluation")
    overall_strengths: list[str] = Field(description="Key strengths across all criteria")
    overall_weaknesses: list[str] = Field(description="Key weaknesses across all criteria")
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
        logger.info("[%s] Initializing CriteriaExtractionAgent...", datetime.now().isoformat())
        
        self._validate_config()
        
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
        
        self.client = AzureOpenAIResponsesClient(
            credential=DefaultAzureCredential(),
            endpoint=endpoint,
            deployment_name=deployment_name,
            api_version="v1"
        )
        
        self.deployment_name = deployment_name
        logger.info("[%s] CriteriaExtractionAgent initialized", datetime.now().isoformat())
    
    def _validate_config(self):
        """Validate required configuration."""
        required_vars = ["AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_DEPLOYMENT_NAME"]
        missing = [var for var in required_vars if not os.getenv(var)]
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
    
    async def extract_criteria(
        self, 
        rfp_content: str,
        progress_callback: Optional[Callable[[str], None]] = None,
        reasoning_effort: str = "high"
    ) -> ExtractedCriteria:
        """
        Extract scoring criteria from the RFP document.
        
        Args:
            rfp_content: The RFP document content in markdown
            progress_callback: Optional callback for progress updates
            reasoning_effort: Reasoning effort level ("low", "medium", "high")
            
        Returns:
            ExtractedCriteria object with all identified criteria
        """
        start_time = time.time()
        logger.info("[%s] Starting criteria extraction (effort: %s)...", datetime.now().isoformat(), reasoning_effort)
        
        if progress_callback:
            progress_callback("Analyzing RFP structure and requirements...")
        
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
            agent = self.client.create_agent(
                instructions=self.SYSTEM_INSTRUCTIONS,
                name="Criteria Extraction Agent",
                additional_chat_options={"reasoning": {"effort": reasoning_effort, "summary": "detailed"}}
            )
            
            if progress_callback:
                progress_callback("Extracting and analyzing criteria...")
            
            result = await agent.run(user_prompt)
            response_text = result.text
            
            # Log token usage
            usage = result.usage_details
            if usage:
                logger.info("[%s] Criteria extraction - Tokens: Input=%d, Output=%d, Total=%d",
                           datetime.now().isoformat(),
                           usage.input_token_count or 0,
                           usage.output_token_count or 0,
                           usage.total_token_count or 0)
            
            # Parse the response
            criteria_data = self._parse_response(response_text)
            
            duration = time.time() - start_time
            logger.info("[%s] Criteria extraction completed in %.2fs - Found %d criteria",
                       datetime.now().isoformat(), duration, len(criteria_data.get("criteria", [])))
            
            return ExtractedCriteria(**criteria_data)
            
        except Exception as e:
            logger.error("[%s] Criteria extraction failed: %s", datetime.now().isoformat(), str(e))
            raise
    
    def _parse_response(self, response_text: str) -> dict:
        """Parse the agent response into a dictionary."""
        text = response_text.strip()
        
        # Remove markdown code blocks
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        
        try:
            data = json.loads(text)
            
            # Validate and normalize weights
            criteria = data.get("criteria", [])
            total_weight = sum(c.get("weight", 0) for c in criteria)
            
            # Normalize if weights don't sum to 100
            if criteria and abs(total_weight - 100) > 0.1:
                logger.warning("[%s] Normalizing weights from %.2f to 100", 
                              datetime.now().isoformat(), total_weight)
                for criterion in criteria:
                    criterion["weight"] = (criterion.get("weight", 0) / total_weight) * 100
                data["total_weight"] = 100.0
            
            return data
            
        except json.JSONDecodeError as e:
            logger.error("[%s] Failed to parse criteria JSON: %s", datetime.now().isoformat(), str(e))
            # Return default structure
            return {
                "rfp_title": "Unknown RFP",
                "rfp_summary": "Failed to extract RFP summary",
                "total_weight": 100.0,
                "criteria": [],
                "extraction_notes": f"Error parsing response: {str(e)}"
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
        logger.info("[%s] Initializing ProposalScoringAgent...", datetime.now().isoformat())
        
        self._validate_config()
        
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
        
        self.client = AzureOpenAIResponsesClient(
            credential=DefaultAzureCredential(),
            endpoint=endpoint,
            deployment_name=deployment_name,
            api_version="v1"
        )
        
        self.deployment_name = deployment_name
        logger.info("[%s] ProposalScoringAgent initialized", datetime.now().isoformat())
    
    def _validate_config(self):
        """Validate required configuration."""
        required_vars = ["AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_DEPLOYMENT_NAME"]
        missing = [var for var in required_vars if not os.getenv(var)]
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
    
    async def score_proposal(
        self,
        criteria: ExtractedCriteria,
        proposal_content: str,
        progress_callback: Optional[Callable[[str], None]] = None,
        reasoning_effort: str = "high"
    ) -> ProposalEvaluationV2:
        """
        Score the proposal against extracted criteria.
        
        Args:
            criteria: ExtractedCriteria from the extraction agent
            proposal_content: The vendor proposal content
            progress_callback: Optional callback for progress updates
            reasoning_effort: Reasoning effort level ("low", "medium", "high")
            
        Returns:
            ProposalEvaluationV2 with complete scoring results
        """
        start_time = time.time()
        logger.info("[%s] Starting proposal scoring against %d criteria (effort: %s)...",
                   datetime.now().isoformat(), len(criteria.criteria), reasoning_effort)
        
        if progress_callback:
            progress_callback("Preparing scoring framework...")
        
        # Format criteria for the system instructions
        criteria_json = json.dumps([
            {
                "criterion_id": c.criterion_id,
                "name": c.name,
                "description": c.description,
                "category": c.category,
                "weight": c.weight,
                "max_score": c.max_score,
                "evaluation_guidance": c.evaluation_guidance
            }
            for c in criteria.criteria
        ], indent=2)
        
        system_instructions = self.SYSTEM_INSTRUCTIONS_TEMPLATE.format(
            criteria_json=criteria_json
        )
        
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
            agent = self.client.create_agent(
                instructions=system_instructions,
                name="Proposal Scoring Agent",
                additional_chat_options={"reasoning": {"effort": reasoning_effort, "summary": "detailed"}}
            )
            
            if progress_callback:
                progress_callback("Scoring proposal against criteria...")
            
            result = await agent.run(user_prompt)
            response_text = result.text
            
            # Log token usage
            usage = result.usage_details
            if usage:
                logger.info("[%s] Proposal scoring - Tokens: Input=%d, Output=%d, Total=%d",
                           datetime.now().isoformat(),
                           usage.input_token_count or 0,
                           usage.output_token_count or 0,
                           usage.total_token_count or 0)
            
            # Parse the response
            evaluation_data = self._parse_response(response_text, criteria)
            
            duration = time.time() - start_time
            logger.info("[%s] Proposal scoring completed in %.2fs - Total score: %.2f",
                       datetime.now().isoformat(), duration, evaluation_data.get("total_score", 0))
            
            return ProposalEvaluationV2(**evaluation_data)
            
        except Exception as e:
            logger.error("[%s] Proposal scoring failed: %s", datetime.now().isoformat(), str(e))
            raise
    
    def _parse_response(self, response_text: str, criteria: ExtractedCriteria) -> dict:
        """Parse the agent response into a dictionary."""
        text = response_text.strip()
        
        # Remove markdown code blocks
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        
        try:
            data = json.loads(text)
            
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
            logger.error("[%s] Failed to parse scoring JSON: %s", datetime.now().isoformat(), str(e))
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
                "risk_assessment": "Unable to assess"
            }


# ============================================================================
# Main V2 Scoring Orchestrator
# ============================================================================

class ScoringAgentV2:
    """
    Multi-Agent RFP Scoring System V2.
    
    Orchestrates two agents:
    1. CriteriaExtractionAgent - Extracts scoring criteria from RFP
    2. ProposalScoringAgent - Scores proposal against criteria
    """
    
    def __init__(self):
        """Initialize the V2 scoring system."""
        logger.info("[%s] Initializing ScoringAgentV2 (Multi-Agent System)...", 
                   datetime.now().isoformat())
        
        self.criteria_agent = CriteriaExtractionAgent()
        self.scoring_agent = ProposalScoringAgent()
        
        logger.info("[%s] ScoringAgentV2 initialized with 2 agents", datetime.now().isoformat())
    
    async def evaluate(
        self,
        rfp_content: str,
        proposal_content: str,
        scoring_guide: str = "",  # Kept for API compatibility but not used in v2
        progress_callback: Optional[Callable[[str], None]] = None,
        reasoning_effort: str = "high"
    ) -> dict:
        """
        Perform full multi-agent evaluation.
        
        Args:
            rfp_content: The RFP document content
            proposal_content: The vendor proposal content
            scoring_guide: (Unused in V2 - criteria extracted from RFP)
            progress_callback: Optional callback for progress updates
            reasoning_effort: Reasoning effort level ("low", "medium", "high")
            
        Returns:
            Dictionary containing complete evaluation results with metadata
        """
        total_start = time.time()
        logger.info("[%s] ====== V2 MULTI-AGENT EVALUATION STARTED (effort: %s) ======", 
                   datetime.now().isoformat(), reasoning_effort)
        
        # Phase 1: Extract criteria from RFP
        phase1_start = time.time()
        if progress_callback:
            progress_callback("Phase 1: Extracting scoring criteria from RFP...")
        
        criteria = await self.criteria_agent.extract_criteria(
            rfp_content,
            progress_callback=progress_callback,
            reasoning_effort=reasoning_effort
        )
        phase1_duration = time.time() - phase1_start
        
        logger.info("[%s] Phase 1 completed in %.2fs - Extracted %d criteria",
                   datetime.now().isoformat(), phase1_duration, len(criteria.criteria))
        
        # Phase 2: Score the proposal
        phase2_start = time.time()
        if progress_callback:
            progress_callback("Phase 2: Scoring proposal against extracted criteria...")
        
        evaluation = await self.scoring_agent.score_proposal(
            criteria,
            proposal_content,
            progress_callback=progress_callback,
            reasoning_effort=reasoning_effort
        )
        phase2_duration = time.time() - phase2_start
        
        logger.info("[%s] Phase 2 completed in %.2fs - Total score: %.2f",
                   datetime.now().isoformat(), phase2_duration, evaluation.total_score)
        
        # Compile final results
        total_duration = time.time() - total_start
        
        results = {
            # Header info (compatible with V1 format where possible)
            "rfp_title": evaluation.rfp_title,
            "supplier_name": evaluation.supplier_name,
            "supplier_site": evaluation.supplier_site,
            "response_id": evaluation.response_id,
            "evaluation_date": evaluation.evaluation_date,
            
            # V2 specific scoring
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
                        "evaluation_guidance": c.evaluation_guidance
                    }
                    for c in criteria.criteria
                ],
                "extraction_notes": criteria.extraction_notes
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
                    "gaps": cs.gaps
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
                "reasoning_effort": reasoning_effort
            }
        }
        
        logger.info("[%s] ====== V2 MULTI-AGENT EVALUATION COMPLETED ======", 
                   datetime.now().isoformat())
        logger.info("[%s] Total duration: %.2fs (Phase 1: %.2fs, Phase 2: %.2fs)",
                   datetime.now().isoformat(), total_duration, phase1_duration, phase2_duration)
        
        return results
