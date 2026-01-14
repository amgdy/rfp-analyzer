"""
Azure Document Intelligence Client for document analysis.

This module provides a client for Azure Document Intelligence service
that extracts markdown content including text, tables, images, and charts.
"""

import os
import logging
import time
from typing import Optional

from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import (
    AnalyzeDocumentRequest,
    ContentFormat,
    AnalyzeResult,
    DocumentAnalysisFeature,
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
        """
        analyze_start = time.time()
        logger.info("[REQ:%s] Starting Document Intelligence analysis...", request_id)
        
        # Configure features - include figures for image/chart analysis
        features = []
        if include_figures:
            features.append(DocumentAnalysisFeature.FIGURES)
        
        try:
            # Use prebuilt-layout model for comprehensive document analysis
            poller = self.client.begin_analyze_document(
                model_id="prebuilt-layout",
                body=file_bytes,
                content_type="application/octet-stream",
                output_content_format=ContentFormat.MARKDOWN,
                features=features if features else None
            )
            
            logger.info("[REQ:%s] Document analysis started, waiting for result...", request_id)
            
            result: AnalyzeResult = poller.result()
            
            analyze_duration = time.time() - analyze_start
            logger.info("[REQ:%s] Document analysis completed in %.2fs", request_id, analyze_duration)
            
            # Extract markdown content
            markdown_content = self._build_markdown_from_result(result, request_id)
            
            logger.info("[REQ:%s] Extracted %d characters of markdown content", 
                       request_id, len(markdown_content))
            
            return markdown_content
            
        except Exception as e:
            logger.error("[REQ:%s] Document analysis failed: %s", request_id, str(e))
            raise
    
    def _build_markdown_from_result(self, result: AnalyzeResult, request_id: str) -> str:
        """
        Build markdown content from analysis result.
        
        Includes the main content plus descriptions of figures, tables, and charts.
        
        Args:
            result: The analyze result from Document Intelligence
            request_id: Request ID for logging
            
        Returns:
            Complete markdown content
        """
        # Start with the main content
        markdown_parts = []
        
        # The content property contains the extracted text in markdown format
        if result.content:
            markdown_parts.append(result.content)
        
        # Add figure/image descriptions if available
        if hasattr(result, 'figures') and result.figures:
            figure_section = self._extract_figure_descriptions(result.figures, request_id)
            if figure_section:
                markdown_parts.append("\n\n---\n\n## Figures and Images\n\n")
                markdown_parts.append(figure_section)
        
        return "".join(markdown_parts)
    
    def _extract_figure_descriptions(self, figures: list, request_id: str) -> str:
        """
        Extract descriptions from figures/images.
        
        Args:
            figures: List of figure objects from the analysis
            request_id: Request ID for logging
            
        Returns:
            Markdown formatted figure descriptions
        """
        if not figures:
            return ""
        
        descriptions = []
        for i, figure in enumerate(figures, 1):
            caption = ""
            if hasattr(figure, 'caption') and figure.caption:
                if hasattr(figure.caption, 'content'):
                    caption = figure.caption.content
                else:
                    caption = str(figure.caption)
            
            # Get any additional elements in the figure
            elements = []
            if hasattr(figure, 'elements') and figure.elements:
                for elem in figure.elements[:5]:  # Limit to avoid too much content
                    if hasattr(elem, 'content'):
                        elements.append(elem.content)
            
            figure_md = f"### Figure {i}"
            if caption:
                figure_md += f"\n**Caption:** {caption}"
            if elements:
                figure_md += f"\n**Content:** {'; '.join(elements)}"
            
            descriptions.append(figure_md)
        
        logger.info("[REQ:%s] Extracted %d figure descriptions", request_id, len(descriptions))
        return "\n\n".join(descriptions)
    
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
        import asyncio
        
        # Run the blocking API call in a thread pool
        return await asyncio.to_thread(
            self.analyze_document, 
            file_bytes, 
            request_id, 
            include_figures
        )
