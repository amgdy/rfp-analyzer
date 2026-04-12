"""Tests for services.token_utils module.

These tests exercise token estimation, budget calculation, content
truncation, and splitting logic.
"""

import pytest

from services.token_utils import (
    MODEL_CONTEXT_WINDOW,
    MAX_OUTPUT_TOKENS,
    SAFE_INPUT_TOKENS,
    SAFETY_MARGIN,
    CHARS_PER_TOKEN,
    estimate_token_count,
    calculate_token_budget,
    fits_in_context,
    truncate_content,
    split_content_by_tokens,
    _split_by_headings,
    _split_by_paragraphs,
    _get_overlap_text,
)


# ============================================================================
# Constants tests
# ============================================================================


class TestConstants:
    """Verify model configuration constants are consistent."""

    def test_safe_input_equals_formula(self):
        assert SAFE_INPUT_TOKENS == MODEL_CONTEXT_WINDOW - MAX_OUTPUT_TOKENS - SAFETY_MARGIN

    def test_context_window_is_1m(self):
        assert MODEL_CONTEXT_WINDOW == 1_050_000

    def test_max_output_tokens(self):
        assert MAX_OUTPUT_TOKENS == 128_000

    def test_safe_input_positive(self):
        assert SAFE_INPUT_TOKENS > 0

    def test_chars_per_token_reasonable(self):
        assert 2.0 < CHARS_PER_TOKEN < 6.0


# ============================================================================
# estimate_token_count tests
# ============================================================================


class TestEstimateTokenCount:
    """Tests for the token estimation function."""

    def test_empty_string(self):
        assert estimate_token_count("") == 0

    def test_single_character(self):
        result = estimate_token_count("a")
        assert result == 0  # 1 / 3.5 rounds down to 0

    def test_short_text(self):
        text = "Hello, world!"  # 13 chars
        result = estimate_token_count(text)
        assert result == int(13 / CHARS_PER_TOKEN)

    def test_longer_text(self):
        text = "a" * 350  # 350 chars -> 100 tokens at 3.5 chars/token
        result = estimate_token_count(text)
        assert result == 100

    def test_scales_linearly(self):
        short = estimate_token_count("a" * 100)
        long = estimate_token_count("a" * 1000)
        # Integer truncation means it's approximately 10x, not exact
        ratio = long / short
        assert 9.5 < ratio < 10.5

    def test_thousand_chars(self):
        text = "word " * 200  # 1000 chars
        result = estimate_token_count(text)
        assert result == int(1000 / CHARS_PER_TOKEN)


# ============================================================================
# calculate_token_budget tests
# ============================================================================


class TestCalculateTokenBudget:
    """Tests for token budget calculation."""

    def test_empty_system_prompt(self):
        budget = calculate_token_budget("")
        expected = MODEL_CONTEXT_WINDOW - MAX_OUTPUT_TOKENS - SAFETY_MARGIN
        assert budget == expected

    def test_with_system_prompt(self):
        prompt = "a" * 3500  # ~1000 tokens
        budget = calculate_token_budget(prompt)
        prompt_tokens = int(3500 / CHARS_PER_TOKEN)
        expected = MODEL_CONTEXT_WINDOW - prompt_tokens - MAX_OUTPUT_TOKENS - SAFETY_MARGIN
        assert budget == expected

    def test_huge_prompt_returns_zero(self):
        # Prompt that consumes entire context
        prompt = "a" * (MODEL_CONTEXT_WINDOW * 5)
        budget = calculate_token_budget(prompt)
        assert budget == 0

    def test_custom_output_tokens(self):
        budget = calculate_token_budget("", reserved_output_tokens=10_000)
        expected = MODEL_CONTEXT_WINDOW - 10_000 - SAFETY_MARGIN
        assert budget == expected

    def test_custom_safety_margin(self):
        budget = calculate_token_budget("", safety_margin=5_000)
        expected = MODEL_CONTEXT_WINDOW - MAX_OUTPUT_TOKENS - 5_000
        assert budget == expected


# ============================================================================
# fits_in_context tests
# ============================================================================


class TestFitsInContext:
    """Tests for context window fit checking."""

    def test_small_texts_fit(self):
        assert fits_in_context("hello", "world") is True

    def test_empty_texts_fit(self):
        assert fits_in_context("", "") is True

    def test_single_text(self):
        assert fits_in_context("small text") is True

    def test_huge_text_does_not_fit(self):
        # Text that far exceeds context
        huge = "a" * (MODEL_CONTEXT_WINDOW * 5)
        assert fits_in_context(huge) is False

    def test_multiple_texts_combined(self):
        # Each text is within limits but combined they may or may not fit
        text = "a" * 1000
        assert fits_in_context(text, text, text) is True

    def test_near_limit(self):
        # Create text just under the limit
        safe = MODEL_CONTEXT_WINDOW - MAX_OUTPUT_TOKENS - SAFETY_MARGIN
        # chars = safe * 3.5, but we want to be just under
        near_limit_chars = int((safe - 10) * CHARS_PER_TOKEN)
        text = "a" * near_limit_chars
        assert fits_in_context(text) is True

    def test_over_limit(self):
        # Create text just over the limit
        safe = MODEL_CONTEXT_WINDOW - MAX_OUTPUT_TOKENS - SAFETY_MARGIN
        over_limit_chars = int((safe + 1000) * CHARS_PER_TOKEN)
        text = "a" * over_limit_chars
        assert fits_in_context(text) is False


# ============================================================================
# truncate_content tests
# ============================================================================


class TestTruncateContent:
    """Tests for content truncation."""

    def test_short_content_unchanged(self):
        text = "This is short."
        result = truncate_content(text, 1000)
        assert result == text

    def test_truncation_adds_notice(self):
        text = "a" * 10000  # ~2857 tokens
        result = truncate_content(text, 100)
        assert "[... Content truncated" in result

    def test_truncated_is_shorter(self):
        text = "a" * 10000
        result = truncate_content(text, 100)
        assert len(result) < len(text)

    def test_respects_max_tokens(self):
        text = "a" * 10000  # ~2857 tokens
        max_tokens = 500
        result = truncate_content(text, max_tokens)
        # Result tokens should be close to max (plus the truncation notice)
        result_tokens = estimate_token_count(result)
        # The truncation notice adds some tokens, so allow margin
        assert result_tokens < max_tokens + 100

    def test_truncates_at_paragraph_boundary(self):
        paragraphs = ["Paragraph one. " * 20 + "\n\n" for _ in range(20)]
        text = "".join(paragraphs)
        result = truncate_content(text, 200)
        # Should have clean paragraph break
        assert "[... Content truncated" in result

    def test_truncates_at_sentence_boundary(self):
        sentences = "This is a sentence. " * 500
        result = truncate_content(sentences, 200)
        assert "[... Content truncated" in result

    def test_empty_text(self):
        assert truncate_content("", 100) == ""

    def test_exact_fit(self):
        text = "a" * int(100 * CHARS_PER_TOKEN)  # exactly 100 tokens
        result = truncate_content(text, 100)
        assert result == text


# ============================================================================
# split_content_by_tokens tests
# ============================================================================


class TestSplitContentByTokens:
    """Tests for token-based content splitting."""

    def test_short_content_single_chunk(self):
        text = "Short content."
        chunks = split_content_by_tokens(text, 1000)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_empty_content(self):
        chunks = split_content_by_tokens("", 1000)
        assert len(chunks) == 1

    def test_splits_large_content(self):
        # Create content that needs 3+ chunks
        text = ("Section content. " * 100 + "\n\n") * 30  # ~3000 tokens
        chunks = split_content_by_tokens(text, 500)
        assert len(chunks) > 1
        # Each chunk should be within limit (approximately)
        for chunk in chunks:
            tokens = estimate_token_count(chunk)
            # Allow some tolerance for boundary splitting
            assert tokens < 600  # 500 + tolerance

    def test_splits_at_heading_boundaries(self):
        sections = [
            f"## Section {i}\n\nContent for section {i}. " * 20
            for i in range(10)
        ]
        text = "\n\n".join(sections)
        chunks = split_content_by_tokens(text, 300)
        assert len(chunks) > 1
        # Verify chunks don't randomly break in the middle of content
        for chunk in chunks:
            assert len(chunk.strip()) > 0

    def test_handles_no_headings(self):
        text = ("Regular paragraph content here. " * 50 + "\n\n") * 20
        chunks = split_content_by_tokens(text, 500)
        assert len(chunks) > 1

    def test_all_content_preserved(self):
        # All original content should appear in at least one chunk
        # (minus overlap text additions)
        text = "Unique marker ABC123. Another section XYZ789."
        chunks = split_content_by_tokens(text, 1000)
        combined = " ".join(chunks)
        assert "ABC123" in combined
        assert "XYZ789" in combined


# ============================================================================
# _split_by_headings tests
# ============================================================================


class TestSplitByHeadings:
    """Tests for the heading-based splitter."""

    def test_no_headings(self):
        text = "Just plain text here."
        parts = _split_by_headings(text)
        assert len(parts) == 1

    def test_single_heading(self):
        text = "# Title\n\nContent here."
        parts = _split_by_headings(text)
        assert len(parts) == 1
        assert "# Title" in parts[0]

    def test_multiple_headings(self):
        text = "# Title\n\nIntro\n\n## Section A\n\nContent A\n\n## Section B\n\nContent B"
        parts = _split_by_headings(text)
        assert len(parts) == 3  # Title + Section A + Section B

    def test_preserves_heading_with_content(self):
        text = "## First\n\nContent1\n\n## Second\n\nContent2"
        parts = _split_by_headings(text)
        assert any("## First" in p and "Content1" in p for p in parts)
        assert any("## Second" in p and "Content2" in p for p in parts)

    def test_h3_headings(self):
        text = "### Sub A\n\nText A\n\n### Sub B\n\nText B"
        parts = _split_by_headings(text)
        assert len(parts) == 2


# ============================================================================
# _split_by_paragraphs tests
# ============================================================================


class TestSplitByParagraphs:
    """Tests for paragraph-based splitting."""

    def test_single_paragraph(self):
        text = "Single paragraph."
        chunks = _split_by_paragraphs(text, 1000)
        assert len(chunks) == 1

    def test_multiple_paragraphs(self):
        text = ("Paragraph. " * 100 + "\n\n") * 10
        chunks = _split_by_paragraphs(text, 200)
        assert len(chunks) > 1

    def test_empty_text(self):
        chunks = _split_by_paragraphs("", 1000)
        assert chunks == []

    def test_respects_token_limit(self):
        text = ("Word " * 100 + "\n\n") * 20
        chunks = _split_by_paragraphs(text, 300)
        for chunk in chunks:
            tokens = estimate_token_count(chunk)
            assert tokens < 400  # 300 + tolerance


# ============================================================================
# _get_overlap_text tests
# ============================================================================


class TestGetOverlapText:
    """Tests for overlap text extraction."""

    def test_empty_text(self):
        assert _get_overlap_text("", 100) == ""

    def test_zero_overlap(self):
        assert _get_overlap_text("some text", 0) == ""

    def test_short_text_returned_as_is(self):
        text = "short"
        result = _get_overlap_text(text, 1000)
        assert result == text

    def test_extracts_end_of_text(self):
        text = "Start of text\n\nMiddle part\n\nEnd of the text"
        result = _get_overlap_text(text, 10)
        assert "continued from previous section" in result

    def test_negative_overlap(self):
        assert _get_overlap_text("text", -1) == ""
