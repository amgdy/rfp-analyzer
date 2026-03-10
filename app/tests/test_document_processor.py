"""Tests for services.document_processor module."""

import pytest

from services.document_processor import ExtractionService


class TestExtractionService:
    """Tests for ExtractionService enum."""

    def test_content_understanding_value(self):
        assert ExtractionService.CONTENT_UNDERSTANDING.value == "content_understanding"

    def test_document_intelligence_value(self):
        assert ExtractionService.DOCUMENT_INTELLIGENCE.value == "document_intelligence"

    def test_is_string_enum(self):
        assert isinstance(ExtractionService.CONTENT_UNDERSTANDING, str)
        assert isinstance(ExtractionService.DOCUMENT_INTELLIGENCE, str)


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
