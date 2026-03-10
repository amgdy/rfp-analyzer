"""Report generation functions for RFP Analyzer."""

import io
import logging

from .utils import format_duration
from .logging_config import get_logger

# Optional PDF support
try:
    from weasyprint import HTML, CSS
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

try:
    import markdown
    MARKDOWN_AVAILABLE = True
except ImportError:
    MARKDOWN_AVAILABLE = False

logger = get_logger(__name__)


def generate_pdf_from_markdown(markdown_content: str, title: str = "RFP Score Report") -> bytes | None:
    """Generate PDF from markdown content.

    Args:
        markdown_content: The markdown content to convert
        title: Title for the PDF document

    Returns:
        PDF bytes if successful, None if PDF generation is not available
    """
    if not PDF_AVAILABLE or not MARKDOWN_AVAILABLE:
        return None

    try:
        # Convert markdown to HTML
        html_content = markdown.markdown(
            markdown_content,
            extensions=['tables', 'fenced_code', 'toc']
        )

        # CSS styling for the PDF
        css = CSS(string='''
            @page {
                size: A4;
                margin: 2cm;
            }
            body {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
                font-size: 11pt;
                line-height: 1.6;
                color: #333;
            }
            h1 {
                color: #1a1a1a;
                border-bottom: 2px solid #0066cc;
                padding-bottom: 10px;
                font-size: 24pt;
            }
            h2 {
                color: #0066cc;
                margin-top: 20px;
                font-size: 18pt;
            }
            h3 {
                color: #333;
                font-size: 14pt;
            }
            table {
                width: 100%;
                border-collapse: collapse;
                margin: 15px 0;
                font-size: 10pt;
            }
            th, td {
                border: 1px solid #ddd;
                padding: 8px;
                text-align: left;
            }
            th {
                background-color: #0066cc;
                color: white;
            }
            tr:nth-child(even) {
                background-color: #f9f9f9;
            }
            code {
                background-color: #f4f4f4;
                padding: 2px 6px;
                border-radius: 3px;
                font-family: "Courier New", monospace;
                font-size: 10pt;
            }
            ul, ol {
                margin-left: 20px;
            }
            li {
                margin-bottom: 5px;
            }
            .score-excellent { color: #28a745; }
            .score-good { color: #17a2b8; }
            .score-average { color: #ffc107; }
            .score-poor { color: #dc3545; }
        ''')

        # Wrap HTML with proper structure
        full_html = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>{title}</title>
        </head>
        <body>
            {html_content}
        </body>
        </html>
        '''

        # Generate PDF
        pdf_buffer = io.BytesIO()
        HTML(string=full_html).write_pdf(pdf_buffer, stylesheets=[css])
        pdf_buffer.seek(0)
        return pdf_buffer.getvalue()

    except Exception as e:
        logger.error(f"Failed to generate PDF: {e}")
        return None


def generate_score_report_v2(results: dict) -> str:
    """Generate a comprehensive markdown score report for V2."""

    # Extract data
    rfp_title = results.get("rfp_title", "RFP Evaluation")
    supplier_name = results.get("supplier_name", "Unknown Vendor")
    supplier_site = results.get("supplier_site", "N/A")
    response_id = results.get("response_id", "N/A")
    evaluation_date = results.get("evaluation_date", "N/A")
    total_score = results.get("total_score", 0)
    grade = results.get("grade", "N/A")
    recommendation = results.get("recommendation", "N/A")

    extracted = results.get("extracted_criteria", {})
    criterion_scores = results.get("criterion_scores", [])

    executive_summary = results.get("executive_summary", "")
    overall_strengths = results.get("overall_strengths", [])
    overall_weaknesses = results.get("overall_weaknesses", [])
    recommendations = results.get("recommendations", [])
    risk_assessment = results.get("risk_assessment", "")

    # Grade badge
    grade_badges = {
        "A": "🟢 **EXCELLENT**",
        "B": "🔵 **GOOD**",
        "C": "🟡 **ACCEPTABLE**",
        "D": "🟠 **BELOW AVERAGE**",
        "F": "🔴 **POOR**"
    }
    grade_badge = grade_badges.get(grade, "⚪ **UNKNOWN**")

    # Build the report
    report = f"""# 📊 RFP Evaluation Report (V2 - Multi Agents)

---

## 📋 Evaluation Summary

| Field | Value |
|-------|-------|
| **RFP Title** | {rfp_title} |
| **Response ID** | {response_id} |
| **Supplier** | {supplier_name} |
| **Supplier Site** | {supplier_site} |
| **Evaluation Date** | {evaluation_date} |
| **Scoring Version** | V2 (Multi-Agent) |

---

## 🎯 Score Overview

| Metric | Value |
|--------|-------|
| **Total Score** | **{total_score:.2f}** / 100 |
| **Grade** | {grade_badge} |
| **Criteria Evaluated** | {len(criterion_scores)} |

### Recommendation

{recommendation}

---

## 🔍 Extracted Criteria Summary

**RFP Summary:** {extracted.get('rfp_summary', 'N/A')}

**Criteria Count:** {extracted.get('criteria_count', len(extracted.get('criteria', [])))}

| ID | Criterion | Category | Weight |
|----|-----------|----------|--------|
"""

    # Add criteria summary
    for c in extracted.get("criteria", []):
        report += f"| {c.get('criterion_id', '')} | {c.get('name', '')} | {c.get('category', '')} | {c.get('weight', 0):.1f}% |\n"

    report += """
---

## 📈 Detailed Scoring Results

| Criterion | Weight | Raw Score | Weighted Score |
|-----------|--------|-----------|----------------|
"""

    # Add score rows
    for cs in criterion_scores:
        raw = cs.get("raw_score", 0)
        weighted = cs.get("weighted_score", 0)
        name = cs.get("criterion_name", cs.get("criterion_id", ""))
        weight = cs.get("weight", 0)

        # Score indicator
        if raw >= 80:
            indicator = "🟢"
        elif raw >= 60:
            indicator = "🟡"
        elif raw >= 40:
            indicator = "🟠"
        else:
            indicator = "🔴"

        report += f"| {indicator} {name} | {weight:.1f}% | {raw:.1f} | **{weighted:.2f}** |\n"

    # Add total row
    total_weighted = sum(cs.get("weighted_score", 0) for cs in criterion_scores)
    report += f"| **TOTAL** | **100%** | - | **{total_weighted:.2f}** |\n"

    report += """
---

## 📝 Criterion-by-Criterion Analysis

"""

    # Detailed analysis for each criterion
    for cs in criterion_scores:
        criterion_id = cs.get("criterion_id", "")
        criterion_name = cs.get("criterion_name", "")
        raw_score = cs.get("raw_score", 0)
        weighted_score = cs.get("weighted_score", 0)
        weight = cs.get("weight", 0)
        evidence = cs.get("evidence", "No evidence provided")
        justification = cs.get("justification", "No justification provided")
        strengths = cs.get("strengths", [])
        gaps = cs.get("gaps", [])

        # Score indicator
        if raw_score >= 80:
            indicator = "🟢"
        elif raw_score >= 60:
            indicator = "🟡"
        elif raw_score >= 40:
            indicator = "🟠"
        else:
            indicator = "🔴"

        report += f"""### {indicator} {criterion_id}. {criterion_name}

| Metric | Value |
|--------|-------|
| Raw Score | **{raw_score:.1f}** / 100 |
| Weight | {weight:.1f}% |
| Weighted Score | **{weighted_score:.2f}** |

**Evidence from Proposal:**
> {evidence}

**Justification:**
{justification}

"""

        if strengths:
            report += "**Strengths:**\n"
            for s in strengths:
                report += f"- ✅ {s}\n"
            report += "\n"

        if gaps:
            report += "**Gaps/Weaknesses:**\n"
            for g in gaps:
                report += f"- ⚠️ {g}\n"
            report += "\n"

        report += "---\n\n"

    # Overall Analysis
    report += """## 💡 Overall Analysis

### Key Strengths
"""
    if overall_strengths:
        for s in overall_strengths:
            report += f"- ✅ {s}\n"
    else:
        report += "- No specific strengths identified\n"

    report += """
### Key Weaknesses
"""
    if overall_weaknesses:
        for w in overall_weaknesses:
            report += f"- ⚠️ {w}\n"
    else:
        report += "- No significant weaknesses identified\n"

    report += """
### Recommendations
"""
    if recommendations:
        for i, r in enumerate(recommendations, 1):
            report += f"{i}. {r}\n"
    else:
        report += "1. No specific recommendations at this time\n"

    # Risk Assessment
    report += f"""
---

## ⚠️ Risk Assessment

{risk_assessment if risk_assessment else "No risk assessment provided."}

---

## 📋 Executive Summary

{executive_summary if executive_summary else "No executive summary provided."}

---

## 📊 Grade Interpretation Guide

| Grade | Score Range | Interpretation |
|-------|-------------|----------------|
| A | 90-100 | ✅ Excellent - Strongly recommended |
| B | 80-89 | ✅ Good - Recommended |
| C | 70-79 | ⚠️ Acceptable - Consider with improvements |
| D | 60-69 | 🟠 Below Average - Significant concerns |
| F | Below 60 | ❌ Poor - Not recommended |

---

*Report generated by RFP Analyzer V2 (Multi-Agent) - Powered by Azure Content Understanding & Microsoft Agent Framework*
"""

    # Add timing metadata if available
    metadata = results.get("_metadata", {})
    if metadata:
        phase1 = format_duration(metadata.get('phase1_criteria_extraction_seconds', 0))
        phase2 = format_duration(metadata.get('phase2_proposal_scoring_seconds', 0))
        total_eval = format_duration(metadata.get('total_duration_seconds', 0))

        report += f"""
---

## ⏱️ Evaluation Timing

| Phase | Duration |
|-------|----------|
| **Criteria Extraction (Agent 1)** | {phase1} |
| **Proposal Scoring (Agent 2)** | {phase2} |
| **Total Evaluation Time** | {total_eval} |
| **Model Deployment** | {metadata.get('model_deployment', 'N/A')} |
| **Analysis Depth** | {metadata.get('reasoning_effort', 'N/A')} |
"""

    return report


def generate_score_report(results: dict) -> str:
    """Generate a comprehensive markdown score report matching the RFP scoring format."""

    # Extract data
    rfp_title = results.get("rfp_title", "RFP Evaluation")
    supplier_name = results.get("supplier_name", "Unknown Vendor")
    supplier_site = results.get("supplier_site", "N/A")
    response_id = results.get("response_id", "N/A")
    scoring_status = results.get("scoring_status", "Completed")
    requirement_score = results.get("requirement_score", 0)
    composite_score = results.get("composite_score", 0)
    overall_rank = results.get("overall_rank", 1)
    requirements = results.get("requirements", [])
    strengths = results.get("strengths", [])
    weaknesses = results.get("weaknesses", [])
    recommendations = results.get("recommendations", [])
    summary = results.get("summary", "")

    # Determine recommendation based on score
    if composite_score >= 60:
        recommendation_badge = "✅ **RECOMMENDED**"
    elif composite_score >= 50:
        recommendation_badge = "⚠️ **CONDITIONALLY RECOMMENDED**"
    elif composite_score >= 40:
        recommendation_badge = "🔶 **REVIEW REQUIRED**"
    else:
        recommendation_badge = "❌ **NOT RECOMMENDED**"

    # Build the report
    report = f"""# 📊 Requirement Scores Report

---

## 📋 Evaluation Summary

| Field | Value |
|-------|-------|
| **Title** | {rfp_title} |
| **Response** | {response_id} |
| **Supplier** | {supplier_name} |
| **Supplier Site** | {supplier_site} |
| **Scoring Status** | {scoring_status} |

---

## 🎯 Score Overview

| Metric | Score |
|--------|-------|
| **Requirement Score** | **{requirement_score:.2f}** / 100 |
| **Composite Score** | **{composite_score:.2f}** / 70 |
| **Overall Rank (Composite)** | {overall_rank} |
| **Recommendation** | {recommendation_badge} |

---

## 📈 Technical Evaluation Criteria

| Requirement | Requirement Text | Evaluation Stage | Target Value | Response Value | Maximum Score | Score | Weight | Weighted Score |
|-------------|------------------|------------------|--------------|----------------|---------------|-------|--------|----------------|
"""

    # Add requirement rows
    for req in requirements:
        req_id = req.get("requirement_id", "")
        req_name = req.get("requirement_name", "")
        req_text = req.get("requirement_text", "")
        eval_stage = req.get("evaluation_stage", "Technical")
        target_val = req.get("target_value", "")
        response_val = req.get("response_value", "")[:50] + "..." if len(req.get("response_value", "")) > 50 else req.get("response_value", "")
        max_score = req.get("maximum_score", 20)
        score = req.get("score", 0)
        weight = req.get("weight", 14.0)
        weighted_score = req.get("weighted_score", 0)

        report += f"| **{req_id}. {req_name}** | {req_text} | {eval_stage} | {target_val} | {response_val} | {max_score} | **{score:.2f}** | {weight:.0f}% | **{weighted_score:.2f}** |\n"

    # Add totals row
    total_max = sum(req.get("maximum_score", 20) for req in requirements) if requirements else 100
    total_score = sum(req.get("score", 0) for req in requirements) if requirements else requirement_score
    total_weight = sum(req.get("weight", 14.0) for req in requirements) if requirements else 70
    total_weighted = sum(req.get("weighted_score", 0) for req in requirements) if requirements else composite_score

    report += f"| **TOTAL** | | | | | **{total_max}** | **{total_score:.2f}** | **{total_weight:.0f}%** | **{total_weighted:.2f}** |\n"

    report += """
---

## 📝 Detailed Requirement Analysis

"""

    # Detailed analysis for each requirement
    for req in requirements:
        req_id = req.get("requirement_id", "")
        req_name = req.get("requirement_name", "")
        score = req.get("score", 0)
        max_score = req.get("maximum_score", 20)
        weighted_score = req.get("weighted_score", 0)
        comments = req.get("comments", "No comments provided")
        response_value = req.get("response_value", "")

        # Score indicator
        pct = (score / max_score * 100) if max_score > 0 else 0
        if pct >= 85:
            indicator = "🟢"
        elif pct >= 65:
            indicator = "🟡"
        elif pct >= 45:
            indicator = "🟠"
        else:
            indicator = "🔴"

        report += f"""### {indicator} {req_id}. {req_name}

| Metric | Value |
|--------|-------|
| Score | **{score:.2f}** / {max_score} |
| Weighted Score | **{weighted_score:.2f}** |
| Performance | {pct:.0f}% |

**Response Summary:** {response_value}

**Evaluation Comments:** {comments}

---

"""

    # Strengths section
    report += """## ✅ Key Strengths

"""
    if strengths:
        for strength in strengths:
            report += f"- {strength}\n"
    else:
        report += "- No specific strengths identified\n"

    # Weaknesses section
    report += """
---

## ⚠️ Areas for Improvement

"""
    if weaknesses:
        for weakness in weaknesses:
            report += f"- {weakness}\n"
    else:
        report += "- No significant weaknesses identified\n"

    # Recommendations section
    report += """
---

## 💡 Recommendations

"""
    if recommendations:
        for i, rec in enumerate(recommendations, 1):
            report += f"{i}. {rec}\n"
    else:
        report += "1. No specific recommendations at this time\n"

    # Executive Summary
    report += f"""
---

## 📋 Executive Summary

{summary if summary else "No executive summary provided."}

---

## 📊 Score Interpretation Guide

| Weighted Score Range | Rating | Recommendation |
|---------------------|--------|----------------|
| 60-70 | Excellent | ✅ Strongly recommended for selection |
| 50-59 | Very Good | ✅ Recommended with minor clarifications |
| 40-49 | Good | ⚠️ Consider with some negotiation |
| 30-39 | Acceptable | 🔶 Review concerns before proceeding |
| Below 30 | Poor | ❌ Not recommended |

---

*Report generated by RFP Analyzer - Powered by Azure Content Understanding & Microsoft Agent Framework*
"""

    # Add timing metadata if available
    metadata = results.get("_metadata", {})
    if metadata:
        api_duration = format_duration(metadata.get('api_call_duration_seconds', 0))
        total_eval_duration = format_duration(metadata.get('total_duration_seconds', 0))
        report += f"""
---

## ⏱️ Evaluation Timing

| Metric | Value |
|--------|-------|
| **Evaluation Timestamp** | {metadata.get('evaluation_timestamp', 'N/A')} |
| **Model Deployment** | {metadata.get('model_deployment', 'N/A')} |
| **Analysis Depth** | {metadata.get('reasoning_effort', 'N/A')} |
| **API Call Duration** | {api_duration} |
| **Total Evaluation Time** | {total_eval_duration} |
"""

    return report
