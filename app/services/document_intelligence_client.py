"""
Azure Document Intelligence Client for document analysis.

This module provides a client for Azure Document Intelligence service
that extracts markdown content including text, tables, images, and charts.
"""

import asyncio
import base64
import os
import logging
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

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s.%(msecs)03d | %(levelname)s | %(name)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


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
        self.endpoint = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT") or os.getenv("AZURE_AI_ENDPOINT")
        
        if not self.endpoint:
            raise ValueError(
                "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT or AZURE_AI_ENDPOINT environment variable is required. "
                "Please set it in your .env file."
            )
        
        logger.info("Using Document Intelligence endpoint: %s...", self.endpoint[:50])
        
        # Check if API key is provided, otherwise use token auth
        api_key = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY") or os.getenv("AZURE_AI_API_KEY")
        
        if api_key:
            self.client = DocumentIntelligenceClient(
                endpoint=self.endpoint,
                credential=AzureKeyCredential(api_key)
            )
            auth_method = "API Key"
        else:
            self.client = DocumentIntelligenceClient(
                endpoint=self.endpoint,
                credential=DefaultAzureCredential()
            )
            auth_method = "Azure AD Token"
        
        logger.info("Authentication method: %s", auth_method)
        
        init_duration = time.time() - init_start
        logger.info("AzureDocumentIntelligenceClient initialized in %.2fs", init_duration)
    
    # Maximum file size in bytes (500 MB for standard tier)
    MAX_FILE_SIZE_BYTES = 500 * 1024 * 1024  # 500 MB
    
    def analyze_document(
        self, 
        file_bytes: bytes, 
        request_id: str = "unknown",
        include_figures: bool = True
    ) -> str:
        """
        Analyze a document and return content as markdown.
        
        Args:
            file_bytes: The document content as bytes
            request_id: Unique request ID for logging correlation
            include_figures: Whether to include figure/image analysis
            
        Returns:
            Extracted content as markdown string
            
        Raises:
            ValueError: If file size exceeds maximum allowed size
        """
        analyze_start = time.time()
        
        # Check file size before sending
        file_size_mb = len(file_bytes) / (1024 * 1024)
        logger.info("[REQ:%s] Starting Document Intelligence analysis (file size: %.2f MB)...", 
                   request_id, file_size_mb)
        
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
            
            poller = self.client.begin_analyze_document(
                model_id="prebuilt-layout",
                body=file_bytes,
                content_type="application/octet-stream",
                output_content_format=DocumentContentFormat.MARKDOWN,
                output=output_options,
            )
            
            logger.info("[REQ:%s] Document analysis started, waiting for result...", request_id)
            
            result: AnalyzeResult = poller.result()
            operation_id = poller.details.get("operation_id")
            
            analyze_duration = time.time() - analyze_start
            logger.info("[REQ:%s] Document analysis completed in %.2fs", request_id, analyze_duration)
            
            # Extract markdown content including figure descriptions
            markdown_content = self._build_markdown_from_result(
                result, 
                request_id, 
                operation_id,
                include_figures
            )
            
            logger.info("[REQ:%s] Extracted %d characters of markdown content", 
                       request_id, len(markdown_content))
            
            return markdown_content
            
        except Exception as e:
            logger.error("[REQ:%s] Document analysis failed: %s", request_id, str(e))
            raise
    
    def _build_markdown_from_result(
        self, 
        result: AnalyzeResult, 
        request_id: str,
        operation_id: str = None,
        include_figures: bool = True
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
            markdown_parts.append(result.content)
        
        # Add figure/image descriptions if available
        if include_figures and hasattr(result, 'figures') and result.figures:
            figure_section = self._extract_figure_descriptions(
                result.figures, 
                request_id,
                result.model_id,
                operation_id
            )
            if figure_section:
                markdown_parts.append("\n\n---\n\n## Figures and Images\n\n")
                markdown_parts.append(figure_section)
        
        return "".join(markdown_parts)
    
    def _extract_figure_descriptions(
        self, 
        figures: list, 
        request_id: str,
        model_id: str = None,
        operation_id: str = None
    ) -> str:
        """
        Extract descriptions from figures/images.
        
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
            figure_id = getattr(figure, 'id', None)
            if figure_id:
                figure_md_parts.append(f"\n**Figure ID:** {figure_id}")
            
            # Get caption if available
            caption = ""
            if hasattr(figure, 'caption') and figure.caption:
                if hasattr(figure.caption, 'content'):
                    caption = figure.caption.content
                else:
                    caption = str(figure.caption)
            if caption:
                figure_md_parts.append(f"\n**Caption:** {caption}")
            
            # Get bounding regions (location info)
            if hasattr(figure, 'bounding_regions') and figure.bounding_regions:
                for region in figure.bounding_regions:
                    page_num = getattr(region, 'page_number', 'unknown')
                    figure_md_parts.append(f"\n**Location:** Page {page_num}")
            
            # Get spans information (text content related to the figure)
            if hasattr(figure, 'spans') and figure.spans:
                span_info = []
                for span in figure.spans:
                    offset = getattr(span, 'offset', None)
                    length = getattr(span, 'length', None)
                    if offset is not None and length is not None:
                        span_info.append(f"offset={offset}, length={length}")
                if span_info:
                    figure_md_parts.append(f"\n**Text Spans:** {'; '.join(span_info)}")
            
            # Get any additional elements in the figure
            elements_content = []
            if hasattr(figure, 'elements') and figure.elements:
                for elem in figure.elements[:10]:  # Limit to avoid too much content
                    if isinstance(elem, str):
                        elements_content.append(elem)
                    elif hasattr(elem, 'content'):
                        elements_content.append(elem.content)
            if elements_content:
                figure_md_parts.append(f"\n**Related Content:** {'; '.join(elements_content)}")
            
            # Get footnotes if available
            if hasattr(figure, 'footnotes') and figure.footnotes:
                footnotes = []
                for fn in figure.footnotes:
                    if hasattr(fn, 'content'):
                        footnotes.append(fn.content)
                    else:
                        footnotes.append(str(fn))
                if footnotes:
                    figure_md_parts.append(f"\n**Footnotes:** {'; '.join(footnotes)}")
            
            descriptions.append("".join(figure_md_parts))
        
        logger.info("[REQ:%s] Extracted %d figure descriptions", request_id, len(descriptions))
        return "\n\n".join(descriptions)
    
    def get_figure_image(
        self,
        model_id: str,
        operation_id: str,
        figure_id: str,
        request_id: str = "unknown"
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
                model_id=model_id,
                result_id=operation_id,
                figure_id=figure_id
            )
            # Read all bytes from the response
            image_bytes = b"".join(response)
            logger.info("[REQ:%s] Retrieved figure image, size: %d bytes", request_id, len(image_bytes))
            return image_bytes
        except Exception as e:
            logger.error("[REQ:%s] Failed to retrieve figure image %s: %s", request_id, figure_id, str(e))
            raise
    
    def analyze_document_with_figures(
        self,
        file_bytes: bytes,
        request_id: str = "unknown"
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
        logger.info("[REQ:%s] Starting Document Intelligence analysis with figures (file size: %.2f MB)...", 
                   request_id, file_size_mb)
        
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
            
            logger.info("[REQ:%s] Document analysis started, waiting for result...", request_id)
            
            result: AnalyzeResult = poller.result()
            operation_id = poller.details.get("operation_id")
            
            analyze_duration = time.time() - analyze_start
            logger.info("[REQ:%s] Document analysis completed in %.2fs", request_id, analyze_duration)
            
            # Extract markdown content
            markdown_content = self._build_markdown_from_result(
                result, 
                request_id, 
                operation_id,
                include_figures=True
            )
            
            # Extract figure images
            figure_images = {}
            if result.figures and operation_id:
                for figure in result.figures:
                    figure_id = getattr(figure, 'id', None)
                    if figure_id:
                        try:
                            image_bytes = self.get_figure_image(
                                model_id=result.model_id,
                                operation_id=operation_id,
                                figure_id=figure_id,
                                request_id=request_id
                            )
                            figure_images[figure_id] = image_bytes
                        except Exception as e:
                            logger.warning("[REQ:%s] Could not retrieve figure %s: %s", 
                                         request_id, figure_id, str(e))
            
            logger.info("[REQ:%s] Extracted %d characters of markdown and %d figure images", 
                       request_id, len(markdown_content), len(figure_images))
            
            return markdown_content, figure_images
            
        except Exception as e:
            logger.error("[REQ:%s] Document analysis with figures failed: %s", request_id, str(e))
            raise
    
    async def analyze_document_with_figures_async(
        self,
        file_bytes: bytes,
        request_id: str = "unknown"
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
            self.analyze_document_with_figures,
            file_bytes,
            request_id
        )
    
    async def analyze_document_async(
        self, 
        file_bytes: bytes, 
        request_id: str = "unknown",
        include_figures: bool = True
    ) -> str:
        """
        Async version of analyze_document for parallel processing.
        
        Args:
            file_bytes: The document content as bytes
            request_id: Unique request ID for logging correlation
            include_figures: Whether to include figure/image analysis
            
        Returns:
            Extracted content as markdown string
        """
        # Run the blocking API call in a thread pool
        return await asyncio.to_thread(
            self.analyze_document, 
            file_bytes, 
            request_id, 
            include_figures
        )
