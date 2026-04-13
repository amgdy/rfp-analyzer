"""
Document Processing Service using Azure AI Services.

This module handles document processing and extraction using either:
- Azure Content Understanding (default)
- Azure Document Intelligence

Both services convert various document formats to markdown.
"""

import os
import time
import uuid
from datetime import datetime
from enum import Enum
from typing import Optional
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

from .content_understanding_client import AzureContentUnderstandingClient
from .document_intelligence_client import AzureDocumentIntelligenceClient
from .logging_config import get_logger
from .token_utils import estimate_token_count
from .utils import clean_extracted_markdown, extract_docx_as_markdown

load_dotenv()

# Get logger from centralized config
logger = get_logger(__name__)


class ExtractionService(str, Enum):
    """Available document extraction services."""

    CONTENT_UNDERSTANDING = "content_understanding"
    DOCUMENT_INTELLIGENCE = "document_intelligence"


# Extensions that need local extraction because DI does not support them.
# Note: only .docx (Office Open XML) is supported by python-docx.
# Old binary .doc files are NOT supported and will be sent to DI as-is
# (DI will reject them with an InvalidContent error — users must convert
# to .docx or .pdf first).
_DOCX_EXTENSIONS = ("docx",)


class DocumentProcessor:
    """
    Document processor using Azure AI Services.

    Supports multiple extraction backends:
    - Azure Content Understanding
    - Azure Document Intelligence

    Processes various document formats and extracts content as markdown.
    """

    def __init__(
        self, service: ExtractionService = ExtractionService.CONTENT_UNDERSTANDING
    ):
        """
        Initialize the document processor with specified service.

        Args:
            service: The extraction service to use (default: Content Understanding)
        """
        logger.info("Initializing DocumentProcessor with service: %s...", service.value)
        init_start = time.time()

        self.service = service
        self.cu_client: Optional[AzureContentUnderstandingClient] = None
        self.di_client: Optional[AzureDocumentIntelligenceClient] = None

        if service == ExtractionService.CONTENT_UNDERSTANDING:
            self._init_content_understanding()
        else:
            self._init_document_intelligence()

        init_duration = time.time() - init_start
        logger.info("DocumentProcessor initialized in %.2fs", init_duration)

    def _init_content_understanding(self):
        """Initialize Azure Content Understanding client."""
        self.endpoint = os.getenv("AZURE_CONTENT_UNDERSTANDING_ENDPOINT")

        if not self.endpoint:
            raise ValueError(
                "AZURE_CONTENT_UNDERSTANDING_ENDPOINT environment variable is required. "
                "Please set it in your .env file."
            )

        logger.info("Using Azure AI endpoint: %s...", self.endpoint[:50])

        # Create token provider using DefaultAzureCredential
        def token_provider():
            credential = DefaultAzureCredential()
            token = credential.get_token("https://cognitiveservices.azure.com/.default")
            return token.token

        # Check if API key is provided, otherwise use token auth
        api_key = os.getenv("AZURE_AI_API_KEY")
        auth_method = "API Key" if api_key else "Azure AD Token"
        logger.info("Authentication method: %s", auth_method)

        self.cu_client = AzureContentUnderstandingClient(
            endpoint=self.endpoint,
            api_version="2025-11-01",
            subscription_key=api_key,
            token_provider=token_provider if not api_key else None,
        )

    def _init_document_intelligence(self):
        """Initialize Azure Document Intelligence client."""
        self.di_client = AzureDocumentIntelligenceClient()

    async def extract_content(self, file_bytes: bytes, filename: str) -> str:
        """
        Extract content from a document and return as markdown.

        Uses the configured extraction service (Content Understanding or Document Intelligence).

        Args:
            file_bytes: The document content as bytes
            filename: The original filename (used to determine file type)

        Returns:
            Extracted content as markdown string
        """
        import asyncio

        # Generate unique request ID for tracking this extraction
        request_id = str(uuid.uuid4())[:8]
        extract_start = time.time()
        logger.info(
            "[REQ:%s] Starting content extraction for: %s (%d bytes) using %s",
            request_id,
            filename,
            len(file_bytes),
            self.service.value,
        )

        # Determine content type based on filename extension
        extension = filename.lower().split(".")[-1] if "." in filename else ""
        logger.info("[REQ:%s] Detected file extension: %s", request_id, extension)

        # Handle plain text and markdown files directly
        if extension in ["txt", "md"]:
            logger.info(
                "[REQ:%s] Processing as plain text/markdown (no Azure API call needed)",
                request_id,
            )
            content = file_bytes.decode("utf-8")
            duration = time.time() - extract_start
            logger.info(
                "[REQ:%s] Text extraction completed in %.3fs (%d chars)",
                request_id,
                duration,
                len(content),
            )
            return content

        # Handle DOCX files locally using python-docx when
        # Document Intelligence is selected (DI does not accept DOCX).
        # Content Understanding supports DOCX natively, so no conversion
        # is needed on that path.
        if extension in _DOCX_EXTENSIONS and self.service == ExtractionService.DOCUMENT_INTELLIGENCE:
            logger.info(
                "[REQ:%s] Converting DOCX to markdown locally (DI does not support DOCX)...",
                request_id,
            )
            try:
                content = await asyncio.to_thread(extract_docx_as_markdown, file_bytes)
            except ValueError:
                # The file has a .docx extension but is not a valid Office
                # Open XML document (e.g. old binary .doc renamed to .docx,
                # corrupted archive, or non-ZIP data).
                logger.error(
                    "[REQ:%s] Local DOCX extraction failed for %s — "
                    "file is not a valid DOCX document",
                    request_id,
                    filename,
                )
                raise
            duration = time.time() - extract_start
            content_tokens = estimate_token_count(content)
            logger.info(
                "[REQ:%s] ✅ DOCX extraction completed in %.3fs (%d chars, ~%d tokens)",
                request_id,
                duration,
                len(content),
                content_tokens,
            )
            return content

        # Use the configured extraction service
        if self.service == ExtractionService.CONTENT_UNDERSTANDING:
            logger.info(
                "[REQ:%s] Processing with Azure Content Understanding (format: %s)...",
                request_id,
                extension,
            )
            content = await asyncio.to_thread(
                self._analyze_with_content_understanding, file_bytes, request_id
            )
        else:
            logger.info(
                "[REQ:%s] Processing with Azure Document Intelligence (format: %s)...",
                request_id,
                extension,
            )
            content = await self.di_client.analyze_document_async(
                file_bytes, request_id
            )

        duration = time.time() - extract_start
        content_tokens = estimate_token_count(content)
        logger.info(
            "[REQ:%s] ✅ Document extraction completed in %.3fs (%d chars, ~%d tokens)",
            request_id,
            duration,
            len(content),
            content_tokens,
        )
        return content

    def _analyze_with_content_understanding(
        self, file_bytes: bytes, request_id: str = "unknown"
    ) -> str:
        """
        Analyze document using Azure Content Understanding.

        Args:
            file_bytes: The document content as bytes
            request_id: Unique request ID for logging correlation

        Returns:
            Extracted content as markdown string
        """
        analyze_start = time.time()
        logger.info(
            "[REQ:%s] 📤 Calling Azure Content Understanding API...", request_id
        )

        # Use the prebuilt-documentSearch analyzer for document analysis
        # This extracts text, tables, and structure from documents as markdown
        api_call_start = time.time()
        response = self.cu_client.begin_analyze_binary_bytes(
            analyzer_id="prebuilt-documentSearch", file_bytes=file_bytes
        )
        api_call_duration = time.time() - api_call_start
        logger.info(
            "[REQ:%s] API call initiated in %.3fs", request_id, api_call_duration
        )

        logger.info("[REQ:%s] ⏳ Polling for analysis result...", request_id)
        poll_start = time.time()
        result = self.cu_client.poll_result(response)
        poll_duration = time.time() - poll_start
        logger.info("[REQ:%s] ✅ Polling completed in %.3fs", request_id, poll_duration)

        # Extract markdown from the first content element
        parse_start = time.time()
        contents = result.get("result", {}).get("contents", [])
        if contents:
            content = contents[0]
            markdown = content.get("markdown", "")

            # Clean up the raw markdown for better readability
            markdown = clean_extracted_markdown(markdown)

            parse_duration = time.time() - parse_start
            analyze_duration = time.time() - analyze_start
            logger.info(
                "[REQ:%s] Azure Content Understanding analysis completed:", request_id
            )
            logger.info(
                "[REQ:%s]   - API initiation: %.3fs", request_id, api_call_duration
            )
            logger.info("[REQ:%s]   - Polling wait: %.3fs", request_id, poll_duration)
            logger.info("[REQ:%s]   - Parse result: %.3fs", request_id, parse_duration)
            logger.info("[REQ:%s]   - Total: %.3fs", request_id, analyze_duration)
            return markdown

        logger.warning("[REQ:%s] ⚠️ No content extracted from document", request_id)
        return ""

    def extract_content_sync(self, file_bytes: bytes, filename: str) -> str:
        """
        Synchronous version of extract_content for non-async contexts.

        Args:
            file_bytes: The document content as bytes
            filename: The original filename (used to determine file type)

        Returns:
            Extracted content as markdown string
        """
        import asyncio

        return asyncio.run(self.extract_content(file_bytes, filename))
