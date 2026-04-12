"""Token estimation and content management utilities for LLM context windows.

Provides token counting, budget management, and content splitting
to ensure documents fit within model context windows.

Configured for GPT-5.4 (1.05M token context, 128K max output).
The context window size can be overridden via the ``MAX_CONTEXT_TOKENS``
environment variable.
"""

import os
import re
from typing import List

from .logging_config import get_logger

logger = get_logger(__name__)


# ============================================================================
# Model Configuration - GPT-5.4
# ============================================================================

def _load_context_window() -> int:
    """Load the model context window size from env or use GPT-5.4 default."""
    env_val = os.getenv("MAX_CONTEXT_TOKENS")
    if env_val:
        try:
            value = int(env_val)
            if value > 0:
                logger.info("Using MAX_CONTEXT_TOKENS from environment: %d", value)
                return value
        except ValueError:
            logger.warning(
                "Invalid MAX_CONTEXT_TOKENS value '%s', using default", env_val
            )
    return 1_050_000


# GPT-5.4 context window: 1,050,000 tokens (overridable via MAX_CONTEXT_TOKENS env var)
MODEL_CONTEXT_WINDOW = _load_context_window()

# Maximum output tokens for GPT-5.4
MAX_OUTPUT_TOKENS = 128_000

# Safety margin to account for tokenizer estimation inaccuracy
SAFETY_MARGIN = 50_000

# Safe input token budget (context window - output tokens - safety margin)
SAFE_INPUT_TOKENS = MODEL_CONTEXT_WINDOW - MAX_OUTPUT_TOKENS - SAFETY_MARGIN

# Characters per token ratio (conservative estimate for English text with formatting)
# GPT models average ~3.5-4 chars/token; we use 3.5 to be conservative (overestimates tokens)
CHARS_PER_TOKEN = 3.5

# Minimum chunk size in tokens (to avoid too-small chunks that lose context)
MIN_CHUNK_TOKENS = 10_000

# Overlap between chunks in tokens (for context continuity across boundaries)
CHUNK_OVERLAP_TOKENS = 500


# ============================================================================
# Token Estimation
# ============================================================================


def estimate_token_count(text: str) -> int:
    """Estimate the number of tokens in a text string.

    Uses a character-based heuristic with a conservative ratio.
    For English text with markdown formatting, this tends to slightly
    overestimate, which provides a safe margin.

    Args:
        text: The text to estimate tokens for

    Returns:
        Estimated number of tokens
    """
    if not text:
        return 0
    return int(len(text) / CHARS_PER_TOKEN)


def calculate_token_budget(
    system_prompt: str,
    reserved_output_tokens: int = MAX_OUTPUT_TOKENS,
    safety_margin: int = SAFETY_MARGIN,
) -> int:
    """Calculate the available token budget for user content.

    Given a system prompt, determines how many tokens remain
    for the user message within the model's context window.

    Args:
        system_prompt: The system prompt/instructions text
        reserved_output_tokens: Tokens reserved for model output
        safety_margin: Additional safety margin in tokens

    Returns:
        Available token budget for user content
    """
    system_tokens = estimate_token_count(system_prompt)
    available = MODEL_CONTEXT_WINDOW - system_tokens - reserved_output_tokens - safety_margin
    return max(0, available)


def fits_in_context(
    *texts: str,
    reserved_output_tokens: int = MAX_OUTPUT_TOKENS,
    safety_margin: int = SAFETY_MARGIN,
) -> bool:
    """Check if the combined texts fit within the model context window.

    Args:
        *texts: One or more text strings (system prompt, user content, etc.)
        reserved_output_tokens: Tokens reserved for output
        safety_margin: Additional safety margin in tokens

    Returns:
        True if all texts combined fit within context window
    """
    total_tokens = sum(estimate_token_count(t) for t in texts)
    available = MODEL_CONTEXT_WINDOW - reserved_output_tokens - safety_margin
    return total_tokens <= available


# ============================================================================
# Content Management
# ============================================================================


def truncate_content(text: str, max_tokens: int) -> str:
    """Truncate content to fit within a token budget.

    Attempts to truncate at natural boundaries (paragraph, sentence)
    when possible to maintain readability.

    Args:
        text: The text to truncate
        max_tokens: Maximum number of tokens allowed

    Returns:
        Truncated text (with truncation notice appended if shortened)
    """
    current_tokens = estimate_token_count(text)
    if current_tokens <= max_tokens:
        return text

    # Calculate approximate character limit
    max_chars = int(max_tokens * CHARS_PER_TOKEN)

    # Try to truncate at natural boundary
    truncated = text[:max_chars]

    # Try paragraph boundary first (within last 20% of text)
    last_para = truncated.rfind("\n\n")
    if last_para > max_chars * 0.8:
        truncated = truncated[:last_para]
    else:
        # Try sentence boundary (within last 10%)
        last_sentence = max(truncated.rfind(". "), truncated.rfind(".\n"))
        if last_sentence > max_chars * 0.9:
            truncated = truncated[: last_sentence + 1]

    logger.warning(
        "Content truncated from ~%d tokens to ~%d tokens (budget: %d)",
        current_tokens,
        estimate_token_count(truncated),
        max_tokens,
    )

    return truncated + "\n\n[... Content truncated due to context window limits ...]"


def split_content_by_tokens(
    text: str,
    max_tokens_per_chunk: int,
    overlap_tokens: int = CHUNK_OVERLAP_TOKENS,
) -> List[str]:
    """Split content into token-bounded chunks at natural boundaries.

    Splits preferring markdown heading boundaries, then paragraph
    boundaries. Each chunk respects the token limit.

    Args:
        text: The text to split
        max_tokens_per_chunk: Maximum tokens per chunk
        overlap_tokens: Number of overlap tokens between chunks

    Returns:
        List of text chunks, each within the token limit
    """
    total_tokens = estimate_token_count(text)
    if total_tokens <= max_tokens_per_chunk:
        return [text]

    # Split into sections by markdown headings
    sections = _split_by_headings(text)

    chunks: List[str] = []
    current_chunk = ""
    current_tokens = 0

    for section in sections:
        section_tokens = estimate_token_count(section)

        if section_tokens > max_tokens_per_chunk:
            # Section is too large, flush current and split by paragraphs
            if current_chunk.strip():
                chunks.append(current_chunk)
                current_chunk = ""
                current_tokens = 0

            sub_chunks = _split_by_paragraphs(section, max_tokens_per_chunk)
            chunks.extend(sub_chunks)
        elif current_tokens + section_tokens > max_tokens_per_chunk:
            # Adding this section would exceed limit, start new chunk
            chunks.append(current_chunk)

            # Start new chunk with overlap from end of previous
            overlap_text = _get_overlap_text(current_chunk, overlap_tokens)
            current_chunk = overlap_text + section
            current_tokens = estimate_token_count(current_chunk)
        else:
            current_chunk += section
            current_tokens += section_tokens

    if current_chunk.strip():
        chunks.append(current_chunk)

    logger.info(
        "Split content (~%d tokens) into %d chunks (max %d tokens/chunk)",
        total_tokens,
        len(chunks),
        max_tokens_per_chunk,
    )

    return chunks


# ============================================================================
# Internal Helpers
# ============================================================================


def _split_by_headings(text: str) -> List[str]:
    """Split text by markdown headings, keeping headings with their content."""
    parts = re.split(r"(?=^#{1,3}\s)", text, flags=re.MULTILINE)
    return [p for p in parts if p.strip()]


def _split_by_paragraphs(text: str, max_tokens: int) -> List[str]:
    """Split text by paragraphs to fit within token limit."""
    paragraphs = text.split("\n\n")
    chunks: List[str] = []
    current_chunk = ""
    current_tokens = 0

    for para in paragraphs:
        para_tokens = estimate_token_count(para)

        if para_tokens > max_tokens:
            # Paragraph itself is too large, flush and truncate
            if current_chunk.strip():
                chunks.append(current_chunk)
                current_chunk = ""
                current_tokens = 0
            chunks.append(truncate_content(para, max_tokens))
        elif current_tokens + para_tokens + 1 > max_tokens:
            # Would exceed limit, start new chunk
            chunks.append(current_chunk)
            current_chunk = para
            current_tokens = para_tokens
        else:
            if current_chunk:
                current_chunk += "\n\n" + para
            else:
                current_chunk = para
            current_tokens += para_tokens + 1  # +1 for separator

    if current_chunk.strip():
        chunks.append(current_chunk)

    return chunks


def _get_overlap_text(text: str, overlap_tokens: int) -> str:
    """Get the last N tokens of text for chunk overlap."""
    if not text or overlap_tokens <= 0:
        return ""

    overlap_chars = int(overlap_tokens * CHARS_PER_TOKEN)
    if len(text) <= overlap_chars:
        return text

    # Try to start at a paragraph boundary
    overlap_text = text[-overlap_chars:]
    para_start = overlap_text.find("\n\n")
    if para_start != -1 and para_start < len(overlap_text) * 0.5:
        overlap_text = overlap_text[para_start + 2 :]

    return "\n\n[... continued from previous section ...]\n\n" + overlap_text
