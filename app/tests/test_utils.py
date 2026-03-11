"""Tests for services.utils module."""

import json
import pytest

from services.utils import parse_json_response, format_duration


# ============================================================================
# parse_json_response tests
# ============================================================================

class TestParseJsonResponse:
    """Tests for the parse_json_response helper."""

    def test_plain_json(self):
        """Parse plain JSON without any code-block wrappers."""
        data = parse_json_response('{"key": "value"}')
        assert data == {"key": "value"}

    def test_json_with_json_code_block(self):
        """Strip ```json ... ``` wrappers."""
        raw = '```json\n{"a": 1}\n```'
        assert parse_json_response(raw) == {"a": 1}

    def test_json_with_generic_code_block(self):
        """Strip ``` ... ``` wrappers (no language hint)."""
        raw = '```\n{"b": 2}\n```'
        assert parse_json_response(raw) == {"b": 2}

    def test_whitespace_padded(self):
        """Handle leading/trailing whitespace."""
        raw = '  \n ```json\n{"c": 3}\n```  \n'
        assert parse_json_response(raw) == {"c": 3}

    def test_nested_json(self):
        """Parse deeply nested JSON correctly."""
        nested = {"level1": {"level2": {"level3": [1, 2, 3]}}}
        raw = f"```json\n{json.dumps(nested)}\n```"
        assert parse_json_response(raw) == nested

    def test_invalid_json_raises(self):
        """Raise JSONDecodeError on malformed content."""
        with pytest.raises(json.JSONDecodeError):
            parse_json_response("not json at all")

    def test_empty_json_object(self):
        """Parse an empty JSON object."""
        assert parse_json_response("{}") == {}

    def test_json_array(self):
        """Parse a JSON array (returns list, which is valid JSON)."""
        result = parse_json_response("[1, 2, 3]")
        assert result == [1, 2, 3]

    def test_only_opening_fence(self):
        """When only opening fence is present, still strips it."""
        # parse_json_response strips startswith ```json but endswith ``` won't match
        # This should still parse if the remaining text is valid JSON
        raw = '```json\n{"d": 4}'
        assert parse_json_response(raw) == {"d": 4}

    def test_real_world_criteria_response(self):
        """Parse a realistic criteria extraction response."""
        response = '''```json
{
    "rfp_title": "Office Renovation RFP",
    "rfp_summary": "Request for proposals for office renovation.",
    "total_weight": 100.0,
    "criteria": [
        {
            "criterion_id": "C-1",
            "name": "Technical Capability",
            "description": "Evaluate technical capabilities",
            "category": "Technical",
            "weight": 40.0,
            "max_score": 100,
            "evaluation_guidance": "Score based on experience"
        },
        {
            "criterion_id": "C-2",
            "name": "Cost",
            "description": "Evaluate pricing",
            "category": "Financial",
            "weight": 60.0,
            "max_score": 100,
            "evaluation_guidance": "Lower is better"
        }
    ],
    "extraction_notes": "Extracted 2 criteria"
}
```'''
        data = parse_json_response(response)
        assert data["rfp_title"] == "Office Renovation RFP"
        assert len(data["criteria"]) == 2
        assert data["criteria"][0]["weight"] == 40.0
        assert data["criteria"][1]["weight"] == 60.0


# ============================================================================
# format_duration tests
# ============================================================================

class TestFormatDuration:
    """Tests for the format_duration helper."""

    def test_zero_seconds(self):
        assert format_duration(0) == "0.0s"

    def test_under_one_second(self):
        assert format_duration(0.5) == "0.5s"

    def test_exactly_one_minute(self):
        assert format_duration(60) == "1m 0.0s"

    def test_one_and_a_half_minutes(self):
        assert format_duration(90) == "1m 30.0s"

    def test_sub_minute(self):
        assert format_duration(45.3) == "45.3s"

    def test_several_minutes(self):
        result = format_duration(125.7)
        assert result == "2m 5.7s"

    def test_large_value(self):
        result = format_duration(3661.2)
        assert result == "61m 1.2s"

    def test_negative_value(self):
        """Negative durations should still format (edge case)."""
        result = format_duration(-5.0)
        assert result == "-5.0s"
