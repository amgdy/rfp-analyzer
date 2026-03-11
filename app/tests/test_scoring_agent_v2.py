"""Tests for services.scoring_agent_v2 module.

These tests exercise the parsing/validation logic without calling Azure APIs.
"""

import json
import pytest

from services.scoring_agent_v2 import (
    ScoringCriterion,
    ExtractedCriteria,
    CriterionScore,
    ProposalEvaluationV2,
    CriteriaExtractionAgent,
    ProposalScoringAgent,
)


# ============================================================================
# Pydantic model tests
# ============================================================================

class TestScoringCriterion:
    """Tests for ScoringCriterion model."""

    def test_create_valid(self):
        c = ScoringCriterion(
            criterion_id="C-1",
            name="Technical",
            description="Tech capabilities",
            category="Technical",
            weight=30.0,
            evaluation_guidance="Score based on tech"
        )
        assert c.criterion_id == "C-1"
        assert c.max_score == 100  # default

    def test_custom_max_score(self):
        c = ScoringCriterion(
            criterion_id="C-1",
            name="Test",
            description="Desc",
            category="Cat",
            weight=10.0,
            max_score=50,
            evaluation_guidance="Guide"
        )
        assert c.max_score == 50


class TestExtractedCriteria:
    """Tests for ExtractedCriteria model."""

    def test_create_with_criteria(self):
        criteria = ExtractedCriteria(
            rfp_title="Test RFP",
            rfp_summary="Summary",
            criteria=[
                ScoringCriterion(
                    criterion_id="C-1", name="T", description="D",
                    category="C", weight=100.0, evaluation_guidance="G"
                )
            ],
            extraction_notes="Notes"
        )
        assert criteria.total_weight == 100.0
        assert len(criteria.criteria) == 1


class TestCriterionScore:
    """Tests for CriterionScore model."""

    def test_create_valid(self):
        cs = CriterionScore(
            criterion_id="C-1",
            criterion_name="Technical",
            weight=50.0,
            raw_score=85.0,
            weighted_score=42.5,
            evidence="Good",
            justification="Strong",
            strengths=["A"],
            gaps=["B"]
        )
        assert cs.weighted_score == 42.5


class TestProposalEvaluationV2:
    """Tests for ProposalEvaluationV2 model."""

    def test_create_valid(self):
        ev = ProposalEvaluationV2(
            rfp_title="RFP",
            supplier_name="Vendor",
            supplier_site="NYC",
            response_id="R-1",
            evaluation_date="2025-01-01",
            total_score=80.0,
            score_percentage=80.0,
            grade="B",
            recommendation="Rec",
            criterion_scores=[],
            executive_summary="Summary",
            overall_strengths=[],
            overall_weaknesses=[],
            recommendations=[],
            risk_assessment="Low"
        )
        assert ev.grade == "B"


# ============================================================================
# _parse_response tests (CriteriaExtractionAgent)
# ============================================================================

class TestCriteriaExtractionAgentParse:
    """Test _parse_response on CriteriaExtractionAgent without Azure calls."""

    @pytest.fixture
    def agent(self, monkeypatch):
        """Create agent with mocked config."""
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://fake.openai.azure.com")
        monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4")
        # We can't fully init without Azure credentials, so we test the method directly
        # by calling it on an instance after patching __init__
        agent = object.__new__(CriteriaExtractionAgent)
        return agent

    def test_parse_valid_json(self, agent):
        response = json.dumps({
            "rfp_title": "Test",
            "rfp_summary": "Summary",
            "total_weight": 100.0,
            "criteria": [
                {"criterion_id": "C-1", "name": "A", "weight": 100.0}
            ],
            "extraction_notes": "OK"
        })
        result = agent._parse_response(response)
        assert result["rfp_title"] == "Test"
        assert len(result["criteria"]) == 1

    def test_parse_normalizes_weights(self, agent):
        response = json.dumps({
            "rfp_title": "Test",
            "rfp_summary": "Summary",
            "total_weight": 200.0,
            "criteria": [
                {"criterion_id": "C-1", "name": "A", "weight": 120.0},
                {"criterion_id": "C-2", "name": "B", "weight": 80.0}
            ],
            "extraction_notes": "OK"
        })
        result = agent._parse_response(response)
        weights = [c["weight"] for c in result["criteria"]]
        assert abs(sum(weights) - 100.0) < 0.1

    def test_parse_with_code_blocks(self, agent):
        response = '```json\n{"rfp_title": "Test", "rfp_summary": "S", "criteria": [], "extraction_notes": "N"}\n```'
        result = agent._parse_response(response)
        assert result["rfp_title"] == "Test"

    def test_parse_invalid_json_returns_default(self, agent):
        result = agent._parse_response("not json")
        assert result["rfp_title"] == "Unknown RFP"
        assert result["criteria"] == []


# ============================================================================
# _parse_response tests (ProposalScoringAgent)
# ============================================================================

class TestProposalScoringAgentParse:
    """Test _parse_response on ProposalScoringAgent without Azure calls."""

    @pytest.fixture
    def agent(self, monkeypatch):
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://fake.openai.azure.com")
        monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4")
        agent = object.__new__(ProposalScoringAgent)
        return agent

    @pytest.fixture
    def criteria(self):
        return ExtractedCriteria(
            rfp_title="Test RFP",
            rfp_summary="Summary",
            criteria=[],
            extraction_notes="OK"
        )

    def test_parse_valid_json(self, agent, criteria):
        response = json.dumps({
            "rfp_title": "Test",
            "supplier_name": "Vendor",
            "supplier_site": "NYC",
            "response_id": "R-1",
            "evaluation_date": "2025-01-01",
            "total_score": 0,
            "score_percentage": 0,
            "grade": "F",
            "recommendation": "No",
            "criterion_scores": [
                {"weighted_score": 40.0},
                {"weighted_score": 35.0}
            ],
            "executive_summary": "OK",
            "overall_strengths": [],
            "overall_weaknesses": [],
            "recommendations": [],
            "risk_assessment": "Low"
        })
        result = agent._parse_response(response, criteria)
        # Should recalculate total score
        assert result["total_score"] == 75.0
        assert result["grade"] == "C"  # 70-79

    def test_parse_sets_grade_a(self, agent, criteria):
        response = json.dumps({
            "criterion_scores": [{"weighted_score": 95.0}],
        })
        result = agent._parse_response(response, criteria)
        assert result["grade"] == "A"

    def test_parse_sets_grade_f(self, agent, criteria):
        response = json.dumps({
            "criterion_scores": [{"weighted_score": 30.0}],
        })
        result = agent._parse_response(response, criteria)
        assert result["grade"] == "F"

    def test_parse_invalid_json_returns_default(self, agent, criteria):
        result = agent._parse_response("broken", criteria)
        assert result["rfp_title"] == "Test RFP"
        assert result["grade"] == "F"
        assert result["total_score"] == 0

    def test_parse_sets_evaluation_date_if_missing(self, agent, criteria):
        response = json.dumps({"criterion_scores": []})
        result = agent._parse_response(response, criteria)
        assert "evaluation_date" in result
        assert result["evaluation_date"] != ""
