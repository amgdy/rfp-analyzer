"""
RFP Scoring Agent using Microsoft Agent Framework.

This module implements an AI agent that evaluates vendor proposals 
against RFP requirements and provides detailed scoring.
"""

import os
import json
import time
from datetime import datetime
from typing import Annotated

from openai import AzureOpenAI
from agent_framework.openai import OpenAIChatClient, OpenAIChatCompletionClient
from azure.identity import DefaultAzureCredential
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from .logging_config import get_logger

load_dotenv()

# Get logger from centralized config
logger = get_logger(__name__)


class RequirementScore(BaseModel):
    """Score for a specific evaluation requirement."""
    requirement_id: str = Field(description="Requirement ID (e.g., 'I-1')")
    requirement_name: str = Field(description="Name of the requirement")
    requirement_text: str = Field(description="Description of what is being evaluated")
    evaluation_stage: str = Field(description="Evaluation stage (e.g., 'Technical')")
    target_value: str = Field(description="Target value if any, otherwise empty")
    response_value: str = Field(description="What was found in the proposal")
    maximum_score: int = Field(description="Maximum possible score (e.g., 20)")
    score: float = Field(description="Actual score awarded (0 to maximum_score)")
    weight: float = Field(description="Weight percentage (e.g., 14.0 for 14%)")
    weighted_score: float = Field(description="Calculated weighted score")
    comments: str = Field(description="Detailed justification for the score")


class EvaluationResult(BaseModel):
    """Complete evaluation result structure matching RFP scoring format."""
    # Header Information
    rfp_title: str = Field(description="Title of the RFP")
    supplier_name: str = Field(description="Name of the vendor/supplier")
    supplier_site: str = Field(description="Location/site of the supplier")
    response_id: str = Field(description="Response/proposal ID")
    
    # Scoring Summary
    scoring_status: str = Field(description="Status of scoring (e.g., 'Completed')")
    requirement_score: float = Field(description="Total requirement score (sum of scores)")
    composite_score: float = Field(description="Composite score including all weights")
    overall_rank: int = Field(description="Ranking position")
    
    # Detailed Scores
    requirements: list[RequirementScore] = Field(description="Scores for each requirement")
    
    # Analysis
    strengths: list[str] = Field(description="Key strengths identified in the proposal")
    weaknesses: list[str] = Field(description="Key weaknesses or gaps identified")
    recommendations: list[str] = Field(description="Recommendations for the proposal")
    summary: str = Field(description="Executive summary of the evaluation")


# Default scoring criteria if no guide is provided
DEFAULT_SCORING_GUIDE = """
## Technical Evaluation Criteria (70% Weight)

### I-1. Agency Reputation (20 points, Weight: 14%)
Evaluates the agency, the team dedicated for the Work, and Reference partners.

### I-2. Methodology (20 points, Weight: 14%)
Evaluates methodology on the approach and the delivery timeline.

### I-3. Themes (20 points, Weight: 14%)
Evaluates the list of proposed themes.

### I-4. Structure (20 points, Weight: 14%)
Evaluates the structure of the proposed contents according to best practices.

### I-5. Examples (20 points, Weight: 14%)
Evaluates examples of recent work done.

## Score Calculation
- Each requirement scored 0-20
- Weighted Score = (Score / 20) × Weight
- Total Technical Weight: 70%
"""


class ScoringAgent:
    """
    AI Agent for evaluating vendor proposals against RFP requirements.
    
    Uses Azure OpenAI with o1/o3 reasoning models to perform intelligent
    analysis and scoring of vendor proposals with deep reasoning capabilities.
    """
    
    def __init__(self):
        """Initialize the scoring agent with Azure OpenAI reasoning model."""
        logger.info("[%s] Initializing ScoringAgent...", datetime.now().isoformat())
        init_start = time.time()
        
        # Validate required environment variables
        self._validate_config()

        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
        
        # Create the Azure OpenAI client for reasoning models (o1/o3)
        self.client = OpenAIChatClient(
            credential=DefaultAzureCredential(),
            azure_endpoint=endpoint,
            model=deployment_name,
            api_version="v1",
        )
        
        # Deployment name for the reasoning model (o3 or o1)
        self.deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
        
        init_duration = time.time() - init_start
        logger.info("[%s] ScoringAgent initialized successfully in %.2fs", 
                   datetime.now().isoformat(), init_duration)
    
    def _get_token_provider(self):
        """Get Azure AD token provider for authentication."""
        from azure.identity import DefaultAzureCredential, get_bearer_token_provider
        credential = DefaultAzureCredential()
        return get_bearer_token_provider(
            credential, "https://cognitiveservices.azure.com/.default"
        )
    
    def _validate_config(self):
        """Validate required configuration."""
        required_vars = [
            "AZURE_OPENAI_ENDPOINT",
            "AZURE_OPENAI_DEPLOYMENT_NAME",
        ]
        
        missing = [var for var in required_vars if not os.getenv(var)]
        
        if missing:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing)}. "
                "Please set them in your .env file."
            )
    
    async def evaluate(
        self, 
        rfp_content: str, 
        proposal_content: str, 
        scoring_guide: str = "",
        progress_callback=None,
        reasoning_effort: str = "high"
    ) -> dict:
        """
        Evaluate a vendor proposal against RFP requirements using Azure OpenAI reasoning model.
        
        Args:
            rfp_content: The RFP document content in markdown
            proposal_content: The vendor proposal content in markdown
            scoring_guide: Optional scoring guide/criteria in markdown
            progress_callback: Optional callback function for progress updates
            reasoning_effort: Reasoning effort level ("low", "medium", "high")
            
        Returns:
            Dictionary containing evaluation results with timing metadata
        """
        evaluate_start = time.time()
        logger.info("[%s] Starting proposal evaluation (effort: %s)...", datetime.now().isoformat(), reasoning_effort)
        logger.info("[%s] RFP content length: %d chars", datetime.now().isoformat(), len(rfp_content))
        logger.info("[%s] Proposal content length: %d chars", datetime.now().isoformat(), len(proposal_content))
        
        # Use default guide if none provided
        if not scoring_guide:
            scoring_guide = DEFAULT_SCORING_GUIDE
            logger.info("[%s] Using default scoring guide", datetime.now().isoformat())
        else:
            logger.info("[%s] Using custom scoring guide (%d chars)", datetime.now().isoformat(), len(scoring_guide))
        
        # Prepare the system instructions and user prompt
        system_instructions = self._get_system_instructions(scoring_guide)
        user_prompt = self._create_evaluation_prompt(rfp_content, proposal_content)
        
        logger.info("[%s] Sending request to Azure OpenAI reasoning model (deployment: %s, effort: %s)...", 
                   datetime.now().isoformat(), self.deployment_name, reasoning_effort)
        
        if progress_callback:
            progress_callback("Initializing AI reasoning engine...")
        
        # Call the reasoning model with specified reasoning effort
        api_start = time.time()
        try:
            agent = self.client.create_agent(
                instructions=system_instructions,
                name="RFP Scoring Agent",

                additional_chat_options={"reasoning": {"effort": reasoning_effort, "summary": "detailed"}}
            )
            agent_result = await agent.run(user_prompt)

            api_duration = time.time() - api_start
            logger.info("[%s] Azure OpenAI API call completed in %.2fs", 
                       datetime.now().isoformat(), api_duration)
            
            # Log token usage from AgentRunResponse.usage_details
            usage = agent_result.usage_details
            if usage:
                input_tokens = usage.input_token_count or 0
                output_tokens = usage.output_token_count or 0
                total_tokens = usage.total_token_count or (input_tokens + output_tokens)
                logger.info("[%s] Token usage - Input: %d, Output: %d, Total: %d",
                           datetime.now().isoformat(),
                           input_tokens,
                           output_tokens,
                           total_tokens)
            
            # AgentRunResponse.text concatenates all message text
            response_text = agent_result.text
            logger.info("[%s] Response received (%d chars)", datetime.now().isoformat(), len(response_text))
            
        except Exception as e:
            logger.error("[%s] Azure OpenAI API call failed: %s", datetime.now().isoformat(), str(e))
            raise
        
        # Parse the response
        parse_start = time.time()
        logger.info("[%s] Parsing evaluation response...", datetime.now().isoformat())
        result = self._parse_response(response_text)
        parse_duration = time.time() - parse_start
        logger.info("[%s] Response parsed in %.2fs", datetime.now().isoformat(), parse_duration)
        
        # Add timing metadata to result
        total_duration = time.time() - evaluate_start
        result["_metadata"] = {
            "evaluation_timestamp": datetime.now().isoformat(),
            "total_duration_seconds": round(total_duration, 2),
            "api_call_duration_seconds": round(api_duration, 2),
            "parse_duration_seconds": round(parse_duration, 2),
            "model_deployment": self.deployment_name,
            "reasoning_effort": reasoning_effort
        }
        
        logger.info("[%s] Evaluation completed successfully in %.2fs", 
                   datetime.now().isoformat(), total_duration)
        
        return result
    
    def _get_system_instructions(self, scoring_guide: str) -> str:
        """Get system instructions for the evaluation agent."""
        return f"""You are an expert RFP (Request for Proposal) analyst and procurement specialist with extensive experience in evaluating vendor proposals for annual reports, creative services, and corporate communications projects.

Your role is to perform a comprehensive, objective evaluation of vendor proposals against RFP requirements, producing a detailed scoring report in a standardized format.

## YOUR EXPERTISE INCLUDES:
- Evaluating agency credentials, team qualifications, and reference partnerships
- Assessing project methodologies, timelines, and delivery approaches  
- Analyzing creative themes, concepts, and innovative proposals
- Reviewing content structure and adherence to best practices
- Examining portfolio examples and past work quality
- Understanding industry benchmarks and competitive standards

## EVALUATION FRAMEWORK

{scoring_guide}

## SCORING METHODOLOGY

For each requirement, you must:

1. **Analyze the RFP Requirement**: Identify what the RFP specifically asks for in each category
2. **Examine the Proposal Response**: Find and quote relevant sections from the vendor proposal
3. **Compare Against Best Practices**: Assess quality, completeness, and professionalism
4. **Assign a Score**: Score from 0-20 based on:
   - 17-20 (Excellent): Exceeds requirements with exceptional quality
   - 13-16 (Good): Fully meets requirements with good quality
   - 9-12 (Adequate): Meets basic requirements with room for improvement
   - 5-8 (Below Average): Partially meets requirements with significant gaps
   - 0-4 (Poor): Fails to meet requirements or missing

5. **Calculate Weighted Score**: weighted_score = (score / 20) × weight

## EVALUATION REQUIREMENTS

### I-1. Agency Reputation (Max: 20, Weight: 14%)
Evaluate:
- Agency's track record and industry standing
- Team credentials and relevant experience
- Quality and relevance of reference partners
- Client testimonials and case study outcomes
- Awards, certifications, and industry recognition

### I-2. Methodology (Max: 20, Weight: 14%)
Evaluate:
- Clarity of proposed approach and work plan
- Feasibility and realism of delivery timeline
- Project management methodology
- Communication and reporting approach
- Risk identification and mitigation strategies

### I-3. Themes (Max: 20, Weight: 14%)
Evaluate:
- Creativity and originality of proposed themes
- Alignment with company brand and values
- Relevance to project objectives
- Innovation and fresh perspective
- Coherence and storytelling potential

### I-4. Structure (Max: 20, Weight: 14%)
Evaluate:
- Logical organization and flow
- Adherence to industry best practices
- Completeness of content coverage
- Visual hierarchy and presentation
- Accessibility and readability

### I-5. Examples (Max: 20, Weight: 14%)
Evaluate:
- Quality of portfolio samples
- Relevance to current project
- Recency of work (last 2-3 years preferred)
- Diversity demonstrating range of capabilities
- Measurable outcomes achieved

## OUTPUT FORMAT

You MUST respond with a valid JSON object in the following exact structure:

```json
{{
  "rfp_title": "Title extracted from the RFP document",
  "supplier_name": "Vendor/company name from proposal",
  "supplier_site": "Location/country from proposal",
  "response_id": "Generate a unique ID like 'RESP-2025-XXXX'",
  "scoring_status": "Completed",
  "requirement_score": <sum of all scores (0-100)>,
  "composite_score": <sum of all weighted scores>,
  "overall_rank": 1,
  "requirements": [
    {{
      "requirement_id": "I-1",
      "requirement_name": "Agency Reputation",
      "requirement_text": "The agency, the team dedicated for the Work, Reference partners.",
      "evaluation_stage": "Technical",
      "target_value": "",
      "response_value": "Brief summary of what proposal offered",
      "maximum_score": 20,
      "score": <0-20>,
      "weight": 14.0,
      "weighted_score": <calculated>,
      "comments": "Detailed justification with specific references to proposal content"
    }},
    {{
      "requirement_id": "I-2",
      "requirement_name": "Methodology",
      "requirement_text": "Methodology on the approach and the delivery timeline.",
      "evaluation_stage": "Technical",
      "target_value": "",
      "response_value": "Brief summary of methodology proposed",
      "maximum_score": 20,
      "score": <0-20>,
      "weight": 14.0,
      "weighted_score": <calculated>,
      "comments": "Detailed justification"
    }},
    {{
      "requirement_id": "I-3",
      "requirement_name": "Themes",
      "requirement_text": "A list of proposed themes.",
      "evaluation_stage": "Technical",
      "target_value": "",
      "response_value": "Brief summary of themes proposed",
      "maximum_score": 20,
      "score": <0-20>,
      "weight": 14.0,
      "weighted_score": <calculated>,
      "comments": "Detailed justification"
    }},
    {{
      "requirement_id": "I-4",
      "requirement_name": "Structure",
      "requirement_text": "The structure of the proposed contents according to best practices.",
      "evaluation_stage": "Technical",
      "target_value": "",
      "response_value": "Brief summary of structure proposed",
      "maximum_score": 20,
      "score": <0-20>,
      "weight": 14.0,
      "weighted_score": <calculated>,
      "comments": "Detailed justification"
    }},
    {{
      "requirement_id": "I-5",
      "requirement_name": "Examples",
      "requirement_text": "Examples of recent work done.",
      "evaluation_stage": "Technical",
      "target_value": "",
      "response_value": "Brief summary of examples provided",
      "maximum_score": 20,
      "score": <0-20>,
      "weight": 14.0,
      "weighted_score": <calculated>,
      "comments": "Detailed justification"
    }}
  ],
  "strengths": [
    "Specific strength 1 with reference to proposal",
    "Specific strength 2 with reference to proposal",
    "Specific strength 3 with reference to proposal"
  ],
  "weaknesses": [
    "Specific weakness/gap 1 with impact assessment",
    "Specific weakness/gap 2 with impact assessment"
  ],
  "recommendations": [
    "Actionable recommendation 1",
    "Actionable recommendation 2",
    "Actionable recommendation 3"
  ],
  "summary": "A comprehensive 2-3 paragraph executive summary covering overall assessment, key findings, and final recommendation."
}}
```

## IMPORTANT GUIDELINES

1. **Be Objective**: Base all scores on evidence found in the documents
2. **Be Specific**: Reference specific sections, quotes, or page numbers when possible
3. **Be Thorough**: Don't skip any evaluation category
4. **Calculate Accurately**: Ensure weighted_score = (score / maximum_score) × weight
5. **Provide Justification**: Every score must have detailed comments explaining the rationale
6. **Extract Metadata**: Pull rfp_title, supplier_name, supplier_site from the actual documents
7. **JSON Only**: Respond with ONLY the JSON object, no additional text or markdown formatting

Remember: Your evaluation will be used for procurement decisions. Be fair, thorough, and professional."""

    def _create_evaluation_prompt(self, rfp_content: str, proposal_content: str) -> str:
        """Create the evaluation prompt."""
        return f"""Please evaluate the following vendor proposal against the RFP requirements.

Perform a comprehensive analysis and score each requirement category as specified in your instructions.

## RFP DOCUMENT
{rfp_content}

---

## VENDOR PROPOSAL  
{proposal_content}

---

IMPORTANT REMINDERS:
1. Extract the RFP title from the RFP document
2. Extract the vendor/supplier name and location from the proposal
3. Score each of the 5 requirements (I-1 through I-5) on a scale of 0-20
4. Calculate weighted scores: weighted_score = (score / 20) × 14.0
5. Sum all scores for requirement_score (max 100)
6. Sum all weighted_scores for composite_score (max 70)
7. Provide detailed comments justifying each score
8. Include specific strengths, weaknesses, and recommendations

Respond with ONLY a valid JSON object matching the exact schema in your instructions."""

    def _parse_response(self, response_text: str) -> dict:
        """Parse the agent response into a structured result."""
        try:
            # Try to extract JSON from the response
            # Handle cases where the response might have markdown code blocks
            text = response_text.strip()

            # Remove markdown code blocks if present
            if text.startswith("```json"):
                text = text[7:]
            elif text.startswith("```"):
                text = text[3:]

            if text.endswith("```"):
                text = text[:-3]

            text = text.strip()

            # Parse JSON
            result = json.loads(text)

            # Return the new format structure
            return {
                "rfp_title": result.get("rfp_title", "RFP Evaluation"),
                "supplier_name": result.get("supplier_name", "Unknown Vendor"),
                "supplier_site": result.get("supplier_site", ""),
                "response_id": result.get("response_id", "RESP-0000"),
                "scoring_status": result.get("scoring_status", "Completed"),
                "requirement_score": result.get("requirement_score", 0),
                "composite_score": result.get("composite_score", 0),
                "overall_rank": result.get("overall_rank", 1),
                "requirements": result.get("requirements", []),
                "strengths": result.get("strengths", []),
                "weaknesses": result.get("weaknesses", []),
                "recommendations": result.get("recommendations", []),
                "summary": result.get("summary", ""),
            }

        except json.JSONDecodeError:
            # If JSON parsing fails, return a default structure with the raw response
            return {
                "rfp_title": "RFP Evaluation",
                "supplier_name": "Unknown Vendor",
                "supplier_site": "",
                "response_id": "RESP-ERROR",
                "scoring_status": "Error",
                "requirement_score": 0,
                "composite_score": 0,
                "overall_rank": 0,
                "requirements": [],
                "strengths": [],
                "weaknesses": [],
                "recommendations": [],
                "summary": f"Error parsing evaluation results. Raw response: {response_text[:500]}...",
            }
