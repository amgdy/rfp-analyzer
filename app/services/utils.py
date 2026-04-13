"""Shared utilities for RFP Analyzer services."""

import io
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


def extract_docx_as_markdown(file_bytes: bytes) -> str:
    """Extract content from a DOCX file as markdown text.

    Uses ``python-docx`` to read paragraphs and tables and produces a
    markdown representation suitable for downstream AI processing.

    Azure Document Intelligence does not natively support ``.docx`` files,
    so this function is used as a local extraction fallback.

    Args:
        file_bytes: The DOCX document content as bytes

    Returns:
        Extracted content as a markdown string

    Raises:
        ImportError: If ``python-docx`` is not installed
        Exception: If the file cannot be parsed as a valid DOCX
    """
    from docx import Document  # python-docx

    _MIN_HEADING_LEVEL = 1
    _MAX_HEADING_LEVEL = 6

    doc = Document(io.BytesIO(file_bytes))
    parts: list[str] = []

    for element in doc.element.body:
        tag = element.tag.split("}")[-1]  # strip namespace

        if tag == "p":
            # Paragraph — check if it has a heading style
            for para in doc.paragraphs:
                if para._element is element:
                    text = para.text.strip()
                    if not text:
                        break
                    style_name = (para.style.name or "").lower() if para.style else ""
                    if style_name.startswith("heading"):
                        # Map heading level: "Heading 1" → "#", "Heading 2" → "##", etc.
                        try:
                            level = int(style_name.split()[-1])
                        except (ValueError, IndexError):
                            level = _MIN_HEADING_LEVEL
                        level = max(_MIN_HEADING_LEVEL, min(level, _MAX_HEADING_LEVEL))
                        parts.append(f"\n{'#' * level} {text}\n")
                    else:
                        parts.append(text)
                    break

        elif tag == "tbl":
            # Table — render as markdown table
            for table in doc.tables:
                if table._element is element:
                    _render_table(table, parts)
                    break

    return clean_extracted_markdown("\n\n".join(parts))


def _render_table(table, parts: list[str]) -> None:
    """Render a python-docx Table as a markdown table into *parts*."""
    rows = table.rows
    if not rows:
        return

    # Build rows of cell text
    md_rows: list[list[str]] = []
    for row in rows:
        md_rows.append([cell.text.strip().replace("\n", " ") for cell in row.cells])

    if not md_rows:
        return

    # Header row
    header = "| " + " | ".join(md_rows[0]) + " |"
    separator = "| " + " | ".join("---" for _ in md_rows[0]) + " |"
    body_lines = [
        "| " + " | ".join(r) + " |"
        for r in md_rows[1:]
    ]

    parts.append("\n".join([header, separator, *body_lines]))
