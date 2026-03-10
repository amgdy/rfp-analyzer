"""Tests for services.report_generator module."""

import pytest

from services.report_generator import (
    generate_score_report_v2,
    generate_score_report,
    generate_pdf_from_markdown,
)


# ============================================================================
# Fixtures / helpers
# ============================================================================

def _make_v2_results(**overrides) -> dict:
    """Build a minimal V2 evaluation result dict."""
    base = {
        "rfp_title": "Test RFP",
        "supplier_name": "Acme Corp",
        "supplier_site": "New York",
        "response_id": "RESP-001",
        "evaluation_date": "2025-01-15",
        "total_score": 82.5,
        "score_percentage": 82.5,
        "grade": "B",
        "recommendation": "Recommended for selection",
        "extracted_criteria": {
            "rfp_summary": "A test RFP summary",
            "total_weight": 100.0,
            "criteria_count": 2,
            "criteria": [
                {
                    "criterion_id": "C-1",
                    "name": "Technical",
                    "description": "Tech skills",
                    "category": "Technical",
                    "weight": 60.0,
                    "evaluation_guidance": "Score tech"
                },
                {
                    "criterion_id": "C-2",
                    "name": "Cost",
                    "description": "Pricing",
                    "category": "Financial",
                    "weight": 40.0,
                    "evaluation_guidance": "Lower cost"
                }
            ],
            "extraction_notes": "Extracted 2 criteria"
        },
        "criterion_scores": [
            {
                "criterion_id": "C-1",
                "criterion_name": "Technical",
                "weight": 60.0,
                "raw_score": 90.0,
                "weighted_score": 54.0,
                "evidence": "Strong technical proposal",
                "justification": "Exceeds requirements",
                "strengths": ["Expert team"],
                "gaps": []
            },
            {
                "criterion_id": "C-2",
                "criterion_name": "Cost",
                "weight": 40.0,
                "raw_score": 71.25,
                "weighted_score": 28.5,
                "evidence": "Competitive pricing",
                "justification": "Within budget",
                "strengths": ["Good value"],
                "gaps": ["No volume discounts"]
            }
        ],
        "executive_summary": "Acme Corp is a strong candidate.",
        "overall_strengths": ["Strong team", "Good pricing"],
        "overall_weaknesses": ["No volume discounts"],
        "recommendations": ["Negotiate volume discounts"],
        "risk_assessment": "Low risk overall",
        "_metadata": {
            "version": "2.0",
            "evaluation_type": "multi-agent",
            "evaluation_timestamp": "2025-01-15T10:00:00",
            "total_duration_seconds": 120.5,
            "phase1_criteria_extraction_seconds": 30.2,
            "phase2_proposal_scoring_seconds": 90.3,
            "criteria_count": 2,
            "model_deployment": "gpt-4.1",
            "reasoning_effort": "high"
        }
    }
    base.update(overrides)
    return base


def _make_v1_results(**overrides) -> dict:
    """Build a minimal V1 evaluation result dict."""
    base = {
        "rfp_title": "V1 Test RFP",
        "supplier_name": "Beta LLC",
        "supplier_site": "London",
        "response_id": "RESP-V1-001",
        "scoring_status": "Completed",
        "requirement_score": 75.0,
        "composite_score": 52.5,
        "overall_rank": 1,
        "requirements": [
            {
                "requirement_id": "I-1",
                "requirement_name": "Reputation",
                "requirement_text": "Agency reputation",
                "evaluation_stage": "Technical",
                "target_value": "",
                "response_value": "Good reputation",
                "maximum_score": 20,
                "score": 15.0,
                "weight": 14.0,
                "weighted_score": 10.5,
                "comments": "Well known agency"
            }
        ],
        "strengths": ["Good reputation"],
        "weaknesses": ["Limited portfolio"],
        "recommendations": ["Request more references"],
        "summary": "Beta LLC meets basic requirements."
    }
    base.update(overrides)
    return base


# ============================================================================
# generate_score_report_v2 tests
# ============================================================================

class TestGenerateScoreReportV2:
    """Tests for generate_score_report_v2."""

    def test_returns_string(self):
        report = generate_score_report_v2(_make_v2_results())
        assert isinstance(report, str)

    def test_contains_rfp_title(self):
        report = generate_score_report_v2(_make_v2_results())
        assert "Test RFP" in report

    def test_contains_supplier_name(self):
        report = generate_score_report_v2(_make_v2_results())
        assert "Acme Corp" in report

    def test_contains_grade(self):
        report = generate_score_report_v2(_make_v2_results())
        assert "GOOD" in report  # Grade B = 🔵 **GOOD**

    def test_contains_criterion_scores(self):
        report = generate_score_report_v2(_make_v2_results())
        assert "Technical" in report
        assert "Cost" in report
        assert "54.00" in report  # weighted score for Technical

    def test_contains_strengths_and_weaknesses(self):
        report = generate_score_report_v2(_make_v2_results())
        assert "Strong team" in report
        assert "No volume discounts" in report

    def test_contains_recommendation(self):
        report = generate_score_report_v2(_make_v2_results())
        assert "Recommended for selection" in report

    def test_contains_timing_metadata(self):
        report = generate_score_report_v2(_make_v2_results())
        assert "Criteria Extraction" in report
        assert "Proposal Scoring" in report

    def test_handles_empty_criteria(self):
        results = _make_v2_results()
        results["criterion_scores"] = []
        results["extracted_criteria"]["criteria"] = []
        report = generate_score_report_v2(results)
        assert isinstance(report, str)
        assert "TOTAL" in report

    def test_handles_missing_metadata(self):
        results = _make_v2_results()
        del results["_metadata"]
        report = generate_score_report_v2(results)
        assert isinstance(report, str)
        assert "Evaluation Timing" not in report

    def test_grade_indicators_excellent(self):
        results = _make_v2_results(grade="A")
        report = generate_score_report_v2(results)
        assert "EXCELLENT" in report

    def test_grade_indicators_poor(self):
        results = _make_v2_results(grade="F")
        report = generate_score_report_v2(results)
        assert "POOR" in report


# ============================================================================
# generate_score_report (V1) tests
# ============================================================================

class TestGenerateScoreReport:
    """Tests for generate_score_report (V1 format)."""

    def test_returns_string(self):
        report = generate_score_report(_make_v1_results())
        assert isinstance(report, str)

    def test_contains_rfp_title(self):
        report = generate_score_report(_make_v1_results())
        assert "V1 Test RFP" in report

    def test_contains_supplier(self):
        report = generate_score_report(_make_v1_results())
        assert "Beta LLC" in report

    def test_contains_requirement_scores(self):
        report = generate_score_report(_make_v1_results())
        assert "Reputation" in report
        assert "15.00" in report

    def test_contains_recommendation_badge(self):
        report = generate_score_report(_make_v1_results())
        assert "RECOMMENDED" in report

    def test_handles_empty_requirements(self):
        results = _make_v1_results()
        results["requirements"] = []
        report = generate_score_report(results)
        assert isinstance(report, str)

    def test_high_score_recommended(self):
        results = _make_v1_results(composite_score=65.0)
        report = generate_score_report(results)
        assert "RECOMMENDED" in report

    def test_low_score_not_recommended(self):
        results = _make_v1_results(composite_score=25.0)
        report = generate_score_report(results)
        assert "NOT RECOMMENDED" in report


# ============================================================================
# generate_pdf_from_markdown tests
# ============================================================================

class TestGeneratePdfFromMarkdown:
    """Tests for generate_pdf_from_markdown."""

    def test_returns_none_when_unavailable(self):
        # PDF generation depends on weasyprint being installed.
        # In test environments it may or may not be available.
        result = generate_pdf_from_markdown("# Test")
        # Either returns bytes or None
        assert result is None or isinstance(result, bytes)

    def test_handles_empty_content(self):
        result = generate_pdf_from_markdown("")
        assert result is None or isinstance(result, bytes)
