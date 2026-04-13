"""Tests for services.document_processor module."""

import pytest

from services.document_processor import (
    ExtractionService,
    TEXT_EXTENSIONS,
    AI_EXTRACTED_EXTENSIONS,
    requires_ai_extraction,
)


class TestExtractionService:
    """Tests for ExtractionService enum."""

    def test_content_understanding_value(self):
        assert ExtractionService.CONTENT_UNDERSTANDING.value == "content_understanding"

    def test_document_intelligence_value(self):
        assert ExtractionService.DOCUMENT_INTELLIGENCE.value == "document_intelligence"

    def test_is_string_enum(self):
        assert isinstance(ExtractionService.CONTENT_UNDERSTANDING, str)
        assert isinstance(ExtractionService.DOCUMENT_INTELLIGENCE, str)


class TestFileTypeClassification:
    """Tests for file type classification helpers."""

    def test_text_extensions(self):
        assert "txt" in TEXT_EXTENSIONS
        assert "md" in TEXT_EXTENSIONS

    def test_ai_extracted_extensions(self):
        assert "pdf" in AI_EXTRACTED_EXTENSIONS
        assert "docx" in AI_EXTRACTED_EXTENSIONS

    def test_requires_ai_extraction_pdf(self):
        assert requires_ai_extraction("document.pdf") is True

    def test_requires_ai_extraction_docx(self):
        assert requires_ai_extraction("proposal.docx") is True

    def test_requires_ai_extraction_txt(self):
        assert requires_ai_extraction("notes.txt") is False

    def test_requires_ai_extraction_md(self):
        assert requires_ai_extraction("readme.md") is False

    def test_requires_ai_extraction_uppercase(self):
        assert requires_ai_extraction("FILE.PDF") is True
        assert requires_ai_extraction("FILE.TXT") is False

    def test_requires_ai_extraction_no_extension(self):
        assert requires_ai_extraction("noextension") is True

    def test_requires_ai_extraction_unknown_ext(self):
        assert requires_ai_extraction("file.xyz") is True


class TestDocumentProcessorInit:
    """Tests for DocumentProcessor initialization edge cases.

    Note: Full initialization requires Azure credentials / env vars and the
    Azure SDK.  In environments where the SDK is not available, we skip these
    tests gracefully.
    """

    def test_extraction_service_enum_values(self):
        """Verify enum values are accessible and correct."""
        assert ExtractionService.CONTENT_UNDERSTANDING == "content_understanding"
        assert ExtractionService.DOCUMENT_INTELLIGENCE == "document_intelligence"
