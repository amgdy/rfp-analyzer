"""Shared utilities for RFP Analyzer services."""

import json
from typing import Any


def parse_json_response(text: str) -> dict[str, Any]:
    """Strip markdown code blocks and parse JSON response text.

    Args:
        text: Raw response text that may contain markdown code blocks

    Returns:
        Parsed JSON as a dictionary

    Raises:
        json.JSONDecodeError: If the text is not valid JSON after stripping
    """
    text = text.strip()

    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    return json.loads(text)


def format_duration(seconds: float) -> str:
    """Format duration in minutes and seconds.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted string like "1m 30.0s" or "45.0s" for durations under a minute
    """
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    remaining_seconds = seconds % 60
    return f"{minutes}m {remaining_seconds:.1f}s"
