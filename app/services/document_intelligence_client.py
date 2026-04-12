"""
Azure Document Intelligence Client for document analysis.

This module provides a client for Azure Document Intelligence service
that extracts markdown content including text, tables, images, and charts.
"""

import asyncio
import base64
import os
import time
from typing import Optional, Dict, List, Tuple

from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import (
    AnalyzeDocumentRequest,
    DocumentContentFormat,
    AnalyzeResult,
    AnalyzeOutputOption,
)
from azure.core.credentials import AzureKeyCredential
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

from .logging_config import get_logger
from .token_utils import estimate_token_count
from .utils import clean_extracted_markdown

load_dotenv()

# Get logger from centralized config
logger = get_logger(__name__)


class AzureDocumentIntelligenceClient:
    """
    Client for Azure Document Intelligence service.

    Extracts content from documents as markdown, including:
    - Text content
    - Tables
    - Images/Figures with descriptions
    - Charts
    """

    def __init__(self):
        """Initialize the Document Intelligence client."""
        logger.info("Initializing AzureDocumentIntelligenceClient...")
        init_start = time.time()

        # Get endpoint from environment - use dedicated DI endpoint or fallback to AI endpoint
        self.endpoint = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT") or os.getenv(
            "AZURE_CONTENT_UNDERSTANDING_ENDPOINT"
        )

        if not self.endpoint:
            raise ValueError(
                "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT or AZURE_CONTENT_UNDERSTANDING_ENDPOINT environment variable is required. "
                "Please set it in your .env file."
            )

        logger.info("Using Document Intelligence endpoint: %s...", self.endpoint[:50])

        # Check if API key is provided, otherwise use token auth
        api_key = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY") or os.getenv(
            "AZURE_AI_API_KEY"
        )

        if api_key:
            self.client = DocumentIntelligenceClient(
                endpoint=self.endpoint, credential=AzureKeyCredential(api_key)
            )
            auth_method = "API Key"
        else:
            self.client = DocumentIntelligenceClient(
                endpoint=self.endpoint, credential=DefaultAzureCredential()
            )
            auth_method = "Azure AD Token"

        logger.info("Authentication method: %s", auth_method)

        init_duration = time.time() - init_start
        logger.info(
            "AzureDocumentIntelligenceClient initialized in %.2fs", init_duration
        )

    # Maximum file size in bytes (500 MB for standard tier)
    MAX_FILE_SIZE_BYTES = 500 * 1024 * 1024  # 500 MB

    # Maximum page count for prebuilt-layout model
    MAX_PAGE_COUNT = 2000

    def analyze_document(
        self,
        file_bytes: bytes,
        request_id: str = "unknown",
        include_figures: bool = True,
        pages: str = None,
    ) -> str:
        """
        Analyze a document and return content as markdown.

        Args:
            file_bytes: The document content as bytes
            request_id: Unique request ID for logging correlation
            include_figures: Whether to include figure/image analysis
            pages: Optional page range to analyze (e.g., "1-100", "1-50,55-100").
                   If None, all pages are analyzed (up to 2000 pages).

        Returns:
            Extracted content as markdown string

        Raises:
            ValueError: If file size exceeds maximum allowed size
        """
        analyze_start = time.time()

        # Check file size before sending
        file_size_mb = len(file_bytes) / (1024 * 1024)
        logger.info(
            "[REQ:%s] Starting Document Intelligence analysis (file size: %.2f MB, pages: %s)...",
            request_id,
            file_size_mb,
            pages or "all",
        )

        if len(file_bytes) > self.MAX_FILE_SIZE_BYTES:
            raise ValueError(
                f"Document size ({file_size_mb:.2f} MB) exceeds maximum allowed size "
                f"({self.MAX_FILE_SIZE_BYTES / (1024 * 1024):.0f} MB). "
                "Please use a smaller document or split it into multiple parts."
            )

        try:
            # Use prebuilt-layout model for comprehensive document analysis
            # Include FIGURES output option to enable figure extraction with cropped images
            output_options = [AnalyzeOutputOption.FIGURES] if include_figures else None

            # Build keyword arguments — include pages only when specified
            analyze_kwargs = {
                "model_id": "prebuilt-layout",
                "body": file_bytes,
                "content_type": "application/octet-stream",
                "output_content_format": DocumentContentFormat.MARKDOWN,
                "output": output_options,
            }
            if pages:
                analyze_kwargs["pages"] = pages
                logger.info("[REQ:%s] Analyzing specific pages: %s", request_id, pages)

            poller = self.client.begin_analyze_document(**analyze_kwargs)

            logger.info(
                "[REQ:%s] Document analysis started, waiting for result "
                "(large documents may take several minutes)...",
                request_id,
            )

            result: AnalyzeResult = poller.result()
            operation_id = poller.details.get("operation_id")

            analyze_duration = time.time() - analyze_start

            # Log page count for large document awareness
            page_count = len(result.pages) if hasattr(result, "pages") and result.pages else 0
            logger.info(
                "[REQ:%s] Document analysis completed in %.2fs (%d pages)",
                request_id,
                analyze_duration,
                page_count,
            )
            if page_count > 100:
                logger.info(
                    "[REQ:%s] Large document detected (%d pages) — extraction may produce substantial content",
                    request_id,
                    page_count,
                )

            # Extract markdown content including figure descriptions
            markdown_content = self._build_markdown_from_result(
                result, request_id, operation_id, include_figures
            )

            # Log content size with estimated token count
            estimated_tokens = estimate_token_count(markdown_content)
            logger.info(
                "[REQ:%s] Extracted %d characters (~%d tokens) of markdown content",
                request_id,
                len(markdown_content),
                estimated_tokens,
            )

            return markdown_content

        except Exception as e:
            logger.error("[REQ:%s] Document analysis failed: %s", request_id, str(e))
            raise

    def _build_markdown_from_result(
        self,
        result: AnalyzeResult,
        request_id: str,
        operation_id: str = None,
        include_figures: bool = True,
    ) -> str:
        """
        Build markdown content from analysis result.

        Includes the main content plus descriptions of figures, tables, and charts.

        Args:
            result: The analyze result from Document Intelligence
            request_id: Request ID for logging
            operation_id: The operation ID for retrieving figure images
            include_figures: Whether to include figure descriptions

        Returns:
            Complete markdown content
        """
        # Start with the main content
        markdown_parts = []

        # The content property contains the extracted text in markdown format
        if result.content:
            markdown_parts.append(self._clean_markdown(result.content))

        # Add table summaries if tables contain structure not fully captured
        # in the main content markdown
        if hasattr(result, "tables") and result.tables:
            table_section = self._extract_table_summaries(
                result.tables, result.content or "", request_id
            )
            if table_section:
                markdown_parts.append("\n\n---\n\n## Tables Summary\n\n")
                markdown_parts.append(table_section)

        # Add figure/image descriptions if available
        if include_figures and hasattr(result, "figures") and result.figures:
            figure_section = self._extract_figure_descriptions(
                result.figures, request_id, result.model_id, operation_id
            )
            if figure_section:
                markdown_parts.append("\n\n---\n\n## Figures and Images\n\n")
                markdown_parts.append(figure_section)

        return "".join(markdown_parts)

    @staticmethod
    def _clean_markdown(content: str) -> str:
        """Clean up extracted markdown for better readability.

        Delegates to the shared ``clean_extracted_markdown`` utility in
        ``services.utils`` for consistent behaviour across extractors.
        """
        return clean_extracted_markdown(content)

    def _extract_table_summaries(
        self,
        tables: list,
        main_content: str,
        request_id: str,
    ) -> str:
        """Extract structured summaries from tables not fully present in main content.

        Document Intelligence already renders most tables as markdown inside
        ``result.content``.  This method adds *supplementary* summaries for
        tables that include metadata (e.g. row/column counts, captions) not
        captured by the inline markdown.

        Args:
            tables: List of table objects from the analysis result
            main_content: The main markdown content (used to avoid duplication)
            request_id: Request ID for logging

        Returns:
            Markdown-formatted table summaries (may be empty string)
        """
        if not tables:
            return ""

        summaries = []
        for idx, table in enumerate(tables, 1):
            row_count = getattr(table, "row_count", 0) or 0
            col_count = getattr(table, "column_count", 0) or 0

            # Only emit a summary for non-trivial tables
            if row_count < 2 and col_count < 2:
                continue

            parts = [f"### Table {idx}"]
            parts.append(f"\n**Dimensions:** {row_count} rows × {col_count} columns")

            # Page location
            regions = getattr(table, "bounding_regions", None)
            if regions:
                pages = sorted({
                    getattr(r, "page_number", None) for r in regions
                } - {None})
                if pages:
                    parts.append(
                        f"\n**Location:** Page {'–'.join(str(p) for p in [pages[0], pages[-1]] if p)}"
                    )

            # Caption
            caption = getattr(table, "caption", None)
            if caption:
                cap_text = getattr(caption, "content", str(caption))
                if cap_text:
                    parts.append(f"\n**Caption:** {cap_text}")

            # Collect header row and first data row for a quick preview
            cells = getattr(table, "cells", []) or []
            header_cells: dict[int, str] = {}
            first_row_cells: dict[int, str] = {}
            for cell in cells:
                r = getattr(cell, "row_index", None)
                c = getattr(cell, "column_index", None)
                text = (getattr(cell, "content", "") or "").strip()
                kind = getattr(cell, "kind", "content")
                if r == 0 or kind == "columnHeader":
                    header_cells.setdefault(c, text)
                elif r == 1:
                    first_row_cells.setdefault(c, text)

            if header_cells:
                headers = [header_cells.get(c, "") for c in range(col_count)]
                parts.append("\n**Headers:** " + " | ".join(h or "—" for h in headers))

            if first_row_cells and row_count > 2:
                first_row = [first_row_cells.get(c, "") for c in range(col_count)]
                parts.append(
                    "\n**First data row (preview):** " + " | ".join(v or "—" for v in first_row)
                )

            summaries.append("".join(parts))

        if summaries:
            logger.info(
                "[REQ:%s] Extracted %d table summaries", request_id, len(summaries)
            )
        return "\n\n".join(summaries)

    def _extract_figure_descriptions(
        self,
        figures: list,
        request_id: str,
        model_id: str = None,
        operation_id: str = None,
    ) -> str:
        """
        Extract descriptions from figures/images/charts.

        Produces clean, readable markdown that gives downstream AI agents
        (e.g. scoring agents) enough context to understand visual content.

        Args:
            figures: List of figure objects from the analysis
            request_id: Request ID for logging
            model_id: The model ID used for analysis
            operation_id: The operation ID for retrieving figure images

        Returns:
            Markdown formatted figure descriptions
        """
        if not figures:
            return ""

        descriptions = []
        for i, figure in enumerate(figures, 1):
            figure_md_parts = [f"### Figure {i}"]

            # Get figure ID for potential image retrieval
            figure_id = getattr(figure, "id", None)
            if figure_id:
                figure_md_parts.append(f"\n**Figure ID:** {figure_id}")

            # Get caption if available — this is the most descriptive element
            caption = ""
            if hasattr(figure, "caption") and figure.caption:
                if hasattr(figure.caption, "content"):
                    caption = figure.caption.content
                else:
                    caption = str(figure.caption)
            if caption:
                figure_md_parts.append(f"\n**Caption:** {caption}")

            # Get bounding regions (location info)
            if hasattr(figure, "bounding_regions") and figure.bounding_regions:
                page_nums = sorted({
                    getattr(r, "page_number", None)
                    for r in figure.bounding_regions
                } - {None})
                if page_nums:
                    figure_md_parts.append(
                        f"\n**Location:** Page {', '.join(str(p) for p in page_nums)}"
                    )

            # Get any additional elements in the figure — provides textual
            # content that was inside or directly associated with the figure
            # (e.g. axis labels, data labels, chart legends).
            elements_content = []
            if hasattr(figure, "elements") and figure.elements:
                for elem in figure.elements[:20]:  # generous limit for complex charts
                    if isinstance(elem, str):
                        elements_content.append(elem)
                    elif hasattr(elem, "content"):
                        elements_content.append(elem.content)
            if elements_content:
                figure_md_parts.append(
                    "\n**Content within figure:**\n"
                    + "\n".join(f"- {c}" for c in elements_content if c.strip())
                )

            # Get footnotes if available
            if hasattr(figure, "footnotes") and figure.footnotes:
                footnotes = []
                for fn in figure.footnotes:
                    if hasattr(fn, "content"):
                        footnotes.append(fn.content)
                    else:
                        footnotes.append(str(fn))
                if footnotes:
                    figure_md_parts.append(
                        "\n**Footnotes:** " + "; ".join(footnotes)
                    )

            # If no caption was found, add a note for the reader
            if not caption and not elements_content:
                figure_md_parts.append(
                    "\n*This figure does not have a machine-readable caption or "
                    "textual content.  Refer to the surrounding document context "
                    "for its meaning.*"
                )

            descriptions.append("".join(figure_md_parts))

        logger.info(
            "[REQ:%s] Extracted %d figure descriptions", request_id, len(descriptions)
        )
        return "\n\n".join(descriptions)

    def get_figure_image(
        self,
        model_id: str,
        operation_id: str,
        figure_id: str,
        request_id: str = "unknown",
    ) -> bytes:
        """
        Retrieve the cropped image for a specific figure.

        Args:
            model_id: The model ID used for analysis
            operation_id: The operation/result ID from the analysis
            figure_id: The figure ID to retrieve
            request_id: Request ID for logging

        Returns:
            Image bytes (PNG format)
        """
        try:
            logger.info("[REQ:%s] Retrieving figure image: %s", request_id, figure_id)
            response = self.client.get_analyze_result_figure(
                model_id=model_id, result_id=operation_id, figure_id=figure_id
            )
            # Read all bytes from the response
            image_bytes = b"".join(response)
            logger.info(
                "[REQ:%s] Retrieved figure image, size: %d bytes",
                request_id,
                len(image_bytes),
            )
            return image_bytes
        except Exception as e:
            logger.error(
                "[REQ:%s] Failed to retrieve figure image %s: %s",
                request_id,
                figure_id,
                str(e),
            )
            raise

    def analyze_document_with_figures(
        self, file_bytes: bytes, request_id: str = "unknown"
    ) -> Tuple[str, Dict[str, bytes]]:
        """
        Analyze a document and return markdown content along with figure images.

        This method extracts both the markdown content and the actual figure images
        as cropped PNG files.

        Args:
            file_bytes: The document content as bytes
            request_id: Unique request ID for logging correlation

        Returns:
            Tuple of (markdown_content, dict of figure_id -> image_bytes)
        """
        analyze_start = time.time()

        # Check file size before sending
        file_size_mb = len(file_bytes) / (1024 * 1024)
        logger.info(
            "[REQ:%s] Starting Document Intelligence analysis with figures (file size: %.2f MB)...",
            request_id,
            file_size_mb,
        )

        if len(file_bytes) > self.MAX_FILE_SIZE_BYTES:
            raise ValueError(
                f"Document size ({file_size_mb:.2f} MB) exceeds maximum allowed size "
                f"({self.MAX_FILE_SIZE_BYTES / (1024 * 1024):.0f} MB). "
                "Please use a smaller document or split it into multiple parts."
            )

        try:
            # Use prebuilt-layout model with FIGURES output option
            poller = self.client.begin_analyze_document(
                model_id="prebuilt-layout",
                body=file_bytes,
                content_type="application/octet-stream",
                output_content_format=DocumentContentFormat.MARKDOWN,
                output=[AnalyzeOutputOption.FIGURES],
            )

            logger.info(
                "[REQ:%s] Document analysis started, waiting for result...", request_id
            )

            result: AnalyzeResult = poller.result()
            operation_id = poller.details.get("operation_id")

            analyze_duration = time.time() - analyze_start
            logger.info(
                "[REQ:%s] Document analysis completed in %.2fs",
                request_id,
                analyze_duration,
            )

            # Extract markdown content
            markdown_content = self._build_markdown_from_result(
                result, request_id, operation_id, include_figures=True
            )

            # Extract figure images
            figure_images = {}
            if result.figures and operation_id:
                for figure in result.figures:
                    figure_id = getattr(figure, "id", None)
                    if figure_id:
                        try:
                            image_bytes = self.get_figure_image(
                                model_id=result.model_id,
                                operation_id=operation_id,
                                figure_id=figure_id,
                                request_id=request_id,
                            )
                            figure_images[figure_id] = image_bytes
                        except Exception as e:
                            logger.warning(
                                "[REQ:%s] Could not retrieve figure %s: %s",
                                request_id,
                                figure_id,
                                str(e),
                            )

            logger.info(
                "[REQ:%s] Extracted %d characters of markdown and %d figure images",
                request_id,
                len(markdown_content),
                len(figure_images),
            )

            return markdown_content, figure_images

        except Exception as e:
            logger.error(
                "[REQ:%s] Document analysis with figures failed: %s", request_id, str(e)
            )
            raise

    async def analyze_document_with_figures_async(
        self, file_bytes: bytes, request_id: str = "unknown"
    ) -> Tuple[str, Dict[str, bytes]]:
        """
        Async version of analyze_document_with_figures.

        Args:
            file_bytes: The document content as bytes
            request_id: Unique request ID for logging correlation

        Returns:
            Tuple of (markdown_content, dict of figure_id -> image_bytes)
        """
        return await asyncio.to_thread(
            self.analyze_document_with_figures, file_bytes, request_id
        )

    async def analyze_document_async(
        self,
        file_bytes: bytes,
        request_id: str = "unknown",
        include_figures: bool = True,
        pages: str = None,
    ) -> str:
        """
        Async version of analyze_document for parallel processing.

        Args:
            file_bytes: The document content as bytes
            request_id: Unique request ID for logging correlation
            include_figures: Whether to include figure/image analysis
            pages: Optional page range to analyze (e.g., "1-100")

        Returns:
            Extracted content as markdown string
        """
        # Run the blocking API call in a thread pool
        return await asyncio.to_thread(
            self.analyze_document, file_bytes, request_id, include_figures, pages
        )
