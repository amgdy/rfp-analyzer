"""Tests for services.scoring_agent module.

These tests exercise the parsing/validation logic without calling Azure APIs.
"""

import json
import pytest

from services.scoring_agent import (
    ScoringCriterion,
    ExtractedCriteria,
    CriterionScore,
    ProposalEvaluation,
    CriteriaExtractionAgent,
    ProposalScoringAgent,
    CONFIDENCE_THRESHOLD,
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
        assert c.confidence == 0.8  # default

    def test_custom_confidence(self):
        c = ScoringCriterion(
            criterion_id="C-1",
            name="Technical",
            description="Tech capabilities",
            category="Technical",
            weight=30.0,
            evaluation_guidance="Score based on tech",
            confidence=0.95,
        )
        assert c.confidence == 0.95

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
        assert criteria.overall_confidence == 0.8  # default


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
        assert cs.confidence == 0.8  # default
        assert cs.reasoning_iterations == 1  # default

    def test_custom_confidence_and_iterations(self):
        cs = CriterionScore(
            criterion_id="C-1",
            criterion_name="Technical",
            weight=50.0,
            raw_score=85.0,
            weighted_score=42.5,
            evidence="Good",
            justification="Strong",
            strengths=["A"],
            gaps=["B"],
            confidence=0.95,
            reasoning_iterations=2,
        )
        assert cs.confidence == 0.95
        assert cs.reasoning_iterations == 2


class TestProposalEvaluation:
    """Tests for ProposalEvaluation model."""

    def test_create_valid(self):
        ev = ProposalEvaluation(
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
        assert ev.overall_confidence == 0.8  # default


class TestConfidenceThreshold:
    """Tests for CONFIDENCE_THRESHOLD constant."""

    def test_threshold_value(self):
        assert CONFIDENCE_THRESHOLD == 0.7

    def test_threshold_is_float(self):
        assert isinstance(CONFIDENCE_THRESHOLD, float)


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

    def test_parse_empty_response_raises(self, agent):
        """Empty model response should raise so retry can kick in."""
        with pytest.raises(RuntimeError, match="empty response text"):
            agent._parse_response("")

    def test_parse_none_response_raises(self, agent):
        """None model response should raise so retry can kick in."""
        with pytest.raises(RuntimeError, match="empty response text"):
            agent._parse_response(None)

    def test_parse_adds_default_confidence(self, agent):
        """Criteria without confidence get default 0.8."""
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
        assert result["criteria"][0]["confidence"] == 0.8
        assert abs(result["overall_confidence"] - 0.8) < 0.01

    def test_parse_preserves_explicit_confidence(self, agent):
        """Criteria with explicit confidence keep their value."""
        response = json.dumps({
            "rfp_title": "Test",
            "rfp_summary": "Summary",
            "total_weight": 100.0,
            "criteria": [
                {"criterion_id": "C-1", "name": "A", "weight": 50.0, "confidence": 0.95},
                {"criterion_id": "C-2", "name": "B", "weight": 50.0, "confidence": 0.55},
            ],
            "extraction_notes": "OK"
        })
        result = agent._parse_response(response)
        assert result["criteria"][0]["confidence"] == 0.95
        assert result["criteria"][1]["confidence"] == 0.55
        assert abs(result["overall_confidence"] - 0.75) < 0.01

    def test_parse_error_fallback_has_zero_confidence(self, agent):
        """Error fallback should have 0 confidence."""
        result = agent._parse_response("not json")
        assert result["overall_confidence"] == 0.0


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
                {"raw_score": 80.0, "weight": 50.0, "weighted_score": 999},
                {"raw_score": 70.0, "weight": 50.0, "weighted_score": 999}
            ],
            "executive_summary": "OK",
            "overall_strengths": [],
            "overall_weaknesses": [],
            "recommendations": [],
            "risk_assessment": "Low"
        })
        result = agent._parse_response(response, criteria)
        # Should recalculate weighted_score = raw_score * weight / 100
        assert result["criterion_scores"][0]["weighted_score"] == 40.0
        assert result["criterion_scores"][1]["weighted_score"] == 35.0
        # Should recalculate total score from weighted scores
        assert result["total_score"] == 75.0
        assert result["grade"] == "C"  # 70-79

    def test_parse_sets_grade_a(self, agent, criteria):
        response = json.dumps({
            "criterion_scores": [{"raw_score": 95.0, "weight": 100.0}],
        })
        result = agent._parse_response(response, criteria)
        assert result["grade"] == "A"

    def test_parse_sets_grade_f(self, agent, criteria):
        response = json.dumps({
            "criterion_scores": [{"raw_score": 30.0, "weight": 100.0}],
        })
        result = agent._parse_response(response, criteria)
        assert result["grade"] == "F"

    def test_parse_recalculates_weighted_score(self, agent, criteria):
        """Verify _parse_response recomputes weighted_score from raw_score * weight / 100."""
        response = json.dumps({
            "criterion_scores": [
                {"raw_score": 90.0, "weight": 40.0, "weighted_score": 0},
                {"raw_score": 80.0, "weight": 60.0, "weighted_score": 0},
            ],
        })
        result = agent._parse_response(response, criteria)
        assert result["criterion_scores"][0]["weighted_score"] == 36.0  # 90*40/100
        assert result["criterion_scores"][1]["weighted_score"] == 48.0  # 80*60/100
        assert result["total_score"] == 84.0  # 36+48
        assert result["grade"] == "B"  # 80-89

    def test_parse_invalid_json_returns_default(self, agent, criteria):
        result = agent._parse_response("broken", criteria)
        assert result["rfp_title"] == "Test RFP"
        assert result["grade"] == "F"
        assert result["total_score"] == 0

    def test_parse_empty_response_raises(self, agent, criteria):
        """Empty model response should raise so retry can kick in."""
        with pytest.raises(RuntimeError, match="empty response text"):
            agent._parse_response("", criteria)

    def test_parse_none_response_raises(self, agent, criteria):
        """None model response should raise so retry can kick in."""
        with pytest.raises(RuntimeError, match="empty response text"):
            agent._parse_response(None, criteria)

    def test_parse_sets_evaluation_date_if_missing(self, agent, criteria):
        response = json.dumps({"criterion_scores": []})
        result = agent._parse_response(response, criteria)
        assert "evaluation_date" in result
        assert result["evaluation_date"] != ""

    def test_parse_adds_default_confidence(self, agent, criteria):
        """Criterion scores without confidence get default 0.8."""
        response = json.dumps({
            "criterion_scores": [
                {"raw_score": 80.0, "weight": 100.0},
            ],
        })
        result = agent._parse_response(response, criteria)
        assert result["criterion_scores"][0]["confidence"] == 0.8
        assert result["criterion_scores"][0]["reasoning_iterations"] == 1
        assert abs(result["overall_confidence"] - 0.8) < 0.01

    def test_parse_preserves_explicit_confidence(self, agent, criteria):
        """Explicit confidence values are kept."""
        response = json.dumps({
            "criterion_scores": [
                {"raw_score": 80.0, "weight": 50.0, "confidence": 0.95},
                {"raw_score": 70.0, "weight": 50.0, "confidence": 0.55},
            ],
        })
        result = agent._parse_response(response, criteria)
        assert result["criterion_scores"][0]["confidence"] == 0.95
        assert result["criterion_scores"][1]["confidence"] == 0.55
        assert abs(result["overall_confidence"] - 0.75) < 0.01

    def test_parse_error_fallback_has_zero_confidence(self, agent, criteria):
        """Error fallback should have 0 confidence."""
        result = agent._parse_response("broken", criteria)
        assert result["overall_confidence"] == 0.0
