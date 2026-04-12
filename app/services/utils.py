"""Shared utilities for RFP Analyzer services."""

import json
import re
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
    if not text or not text.strip():
        raise json.JSONDecodeError(
            "Empty response text — the model returned no content",
            doc=text or "",
            pos=0,
        )
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


def clean_extracted_markdown(markdown: str) -> str:
    """Clean extracted markdown from Azure document processors.

    Fixes common issues produced by Document Intelligence and
    Content Understanding:
    - Collapses excessive blank lines
    - Ensures headers have surrounding blank lines
    - Normalises non-breaking / special whitespace
    - Strips trailing whitespace per line

    Unlike :func:`clean_extracted_text`, this preserves full markdown
    formatting (headers, tables, emphasis, etc.) and is intended for
    the extracted content that will be fed to AI agents.

    Args:
        markdown: Raw markdown from an Azure document processor

    Returns:
        Cleaned markdown string
    """
    if not markdown:
        return ""

    # Collapse runs of 3+ blank lines into 2
    cleaned = re.sub(r"\n{4,}", "\n\n\n", markdown)

    # Ensure headers (#) are preceded by a blank line unless at start
    cleaned = re.sub(r"([^\n])\n(#{1,6} )", r"\1\n\n\2", cleaned)

    # Normalise non-breaking / special spaces
    cleaned = cleaned.replace("\u00a0", " ")

    # Strip trailing whitespace on each line
    cleaned = "\n".join(line.rstrip() for line in cleaned.split("\n"))

    return cleaned.strip()


def clean_extracted_text(text: str) -> str:
    """Clean extracted document text for executive-ready display.

    Strips HTML tags, excessive whitespace, stray markup artifacts,
    and normalises the text so it reads cleanly in a Streamlit UI.

    Args:
        text: Raw extracted text that may contain HTML/markup

    Returns:
        Cleaned plain text suitable for display
    """
    if not text:
        return ""

    # Remove HTML tags
    cleaned = re.sub(r"<[^>]+>", "", text)

    # Remove HTML entities
    cleaned = re.sub(r"&[a-zA-Z]+;", " ", cleaned)
    cleaned = re.sub(r"&#\d+;", " ", cleaned)

    # Remove XML processing instructions / CDATA
    cleaned = re.sub(r"<!\[CDATA\[.*?\]\]>", "", cleaned, flags=re.DOTALL)
    cleaned = re.sub(r"<\?xml[^>]*\?>", "", cleaned)

    # Remove stray markdown image references that are just noise
    cleaned = re.sub(r"!\[(?:image|figure|img)?\]\([^)]*\)", "", cleaned)

    # Remove base64 data URIs (very long inline images)
    cleaned = re.sub(r"data:[a-zA-Z0-9/+;,=]+", "", cleaned)

    # Collapse runs of whitespace (but preserve paragraph breaks)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    # Strip leading/trailing whitespace from each line
    cleaned = "\n".join(line.strip() for line in cleaned.splitlines())

    # Remove fully blank lines at start/end
    cleaned = cleaned.strip()

    return cleaned
