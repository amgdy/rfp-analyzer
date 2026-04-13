"""Tests for services.comparison_agent module.

Tests exercise parsing/validation logic without calling Azure APIs.
"""

import json
import pytest
from datetime import datetime

from services.comparison_agent import (
    VendorRanking,
    CriterionComparison,
    ComparisonResult,
    ComparisonAgent,
    generate_word_report,
    generate_full_analysis_report,
)


# ============================================================================
# Pydantic model tests
# ============================================================================

class TestVendorRanking:
    def test_create_valid(self):
        vr = VendorRanking(
            rank=1,
            vendor_name="Acme",
            total_score=85.0,
            grade="B",
            key_strengths=["Good"],
            key_concerns=["Cost"],
            recommendation="Recommended"
        )
        assert vr.rank == 1
        assert vr.vendor_name == "Acme"


class TestCriterionComparison:
    def test_create_valid(self):
        cc = CriterionComparison(
            criterion_id="C-1",
            criterion_name="Technical",
            weight=40.0,
            best_vendor="Acme",
            worst_vendor="Beta",
            score_range="70-90",
            insights="Acme excels"
        )
        assert cc.best_vendor == "Acme"


class TestComparisonResult:
    def test_create_valid(self):
        cr = ComparisonResult(
            rfp_title="RFP",
            comparison_date="2025-01-15",
            total_vendors=2,
            vendor_rankings=[],
            criterion_comparisons=[],
            winner_summary="Acme wins",
            comparison_insights=[],
            selection_recommendation="Select Acme",
            risk_comparison="Low risk"
        )
        assert cr.total_vendors == 2


# ============================================================================
# ComparisonAgent._parse_response tests
# ============================================================================

class TestComparisonAgentParse:
    """Test _parse_response on ComparisonAgent without Azure calls."""

    @pytest.fixture
    def agent(self, monkeypatch):
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://fake.openai.azure.com")
        monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4")
        agent = object.__new__(ComparisonAgent)
        return agent

    def test_parse_valid_json(self, agent):
        response = json.dumps({
            "rfp_title": "Test RFP",
            "comparison_date": "2025-01-15",
            "total_vendors": 2,
            "vendor_rankings": [],
            "criterion_comparisons": [],
            "winner_summary": "Acme",
            "comparison_insights": ["Insight 1"],
            "selection_recommendation": "Select Acme",
            "risk_comparison": "Low"
        })
        result = agent._parse_response(response)
        assert result["rfp_title"] == "Test RFP"
        assert result["total_vendors"] == 2

    def test_parse_with_code_blocks(self, agent):
        inner = {"rfp_title": "T", "total_vendors": 1}
        response = f'```json\n{json.dumps(inner)}\n```'
        result = agent._parse_response(response)
        assert result["rfp_title"] == "T"

    def test_parse_invalid_json_returns_default(self, agent):
        result = agent._parse_response("not json")
        assert result["rfp_title"] == "Unknown RFP"
        assert result["total_vendors"] == 0
        assert result["vendor_rankings"] == []

    def test_parse_empty_response_raises(self, agent):
        """Empty model response should raise so retry can kick in."""
        with pytest.raises(RuntimeError, match="empty response text"):
            agent._parse_response("")

    def test_parse_none_response_raises(self, agent):
        """None model response should raise so retry can kick in."""
        with pytest.raises(RuntimeError, match="empty response text"):
            agent._parse_response(None)


# ============================================================================
# ComparisonAgent.generate_csv_report tests
# ============================================================================

class TestGenerateCsvReport:
    @pytest.fixture
    def agent(self, monkeypatch):
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://fake.openai.azure.com")
        monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4")
        agent = object.__new__(ComparisonAgent)
        return agent

    def test_csv_contains_headers(self, agent):
        comparison = {
            "rfp_title": "Test",
            "comparison_date": "2025-01-15",
            "total_vendors": 1,
            "vendor_rankings": [
                {"rank": 1, "vendor_name": "Acme", "total_score": 85.0,
                 "grade": "B", "recommendation": "Go"}
            ],
            "comparison_insights": ["Good"],
            "selection_recommendation": "Acme"
        }
        evaluations = [
            {
                "supplier_name": "Acme",
                "total_score": 85.0,
                "criterion_scores": [
                    {"criterion_name": "Tech", "raw_score": 90.0, "weight": 60.0}
                ]
            }
        ]
        csv = agent.generate_csv_report(comparison, evaluations)
        assert "VENDOR RANKINGS" in csv
        assert "Acme" in csv
        assert "Tech" in csv


# ============================================================================
# generate_word_report tests
# ============================================================================

class TestGenerateWordReport:
    def test_returns_bytes_or_none(self):
        evaluation = {
            "rfp_title": "Test",
            "supplier_name": "Acme",
            "total_score": 80.0,
            "grade": "B",
            "evaluation_date": "2025-01-15",
            "recommendation": "Recommended",
            "criterion_scores": [],
            "overall_strengths": ["Good"],
            "overall_weaknesses": ["Cost"],
            "recommendations": ["Negotiate"],
            "executive_summary": "Summary",
            "risk_assessment": "Low"
        }
        result = generate_word_report(evaluation)
        # python-docx may or may not be installed
        assert result is None or isinstance(result, bytes)


class TestGenerateFullAnalysisReport:
    def test_returns_bytes_or_none(self):
        comparison = {
            "comparison_date": "2025-01-15",
            "rfp_title": "Test",
            "total_vendors": 1,
            "vendor_rankings": [],
            "criterion_comparisons": [],
            "winner_summary": "",
            "comparison_insights": [],
            "selection_recommendation": "",
            "risk_comparison": ""
        }
        evaluations = [{
            "supplier_name": "Acme",
            "total_score": 80.0,
            "grade": "B",
            "criterion_scores": [],
            "executive_summary": "",
            "overall_strengths": [],
            "overall_weaknesses": [],
            "recommendations": []
        }]
        result = generate_full_analysis_report(comparison, evaluations)
        assert result is None or isinstance(result, bytes)
