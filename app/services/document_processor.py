"""
Document Processing Service using Azure Content Understanding.

This module handles document processing and extraction using Azure Content Understanding
to convert various document formats to markdown.
"""

import os
import logging
import time
from datetime import datetime
from unittest import result
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

from .content_understanding_client import AzureContentUnderstandingClient

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s.%(msecs)03d | %(levelname)s | %(name)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class DocumentProcessor:
    """
    Document processor using Azure Content Understanding.
    
    Processes various document formats and extracts content as markdown.
    """
    
    def __init__(self):
        """Initialize the document processor with Azure credentials."""
        logger.info("[%s] Initializing DocumentProcessor...", datetime.now().isoformat())
        init_start = time.time()
        
        self.endpoint = os.getenv("AZURE_AI_ENDPOINT")
        
        if not self.endpoint:
            raise ValueError(
                "AZURE_AI_ENDPOINT environment variable is required. "
                "Please set it in your .env file."
            )
        
        logger.info("[%s] Using Azure AI endpoint: %s", datetime.now().isoformat(), self.endpoint[:50] + "...")
        
        # Create token provider using DefaultAzureCredential
        def token_provider():
            credential = DefaultAzureCredential()
            token = credential.get_token("https://cognitiveservices.azure.com/.default")
            return token.token
        
        # Check if API key is provided, otherwise use token auth
        api_key = os.getenv("AZURE_AI_API_KEY")
        auth_method = "API Key" if api_key else "Azure AD Token"
        logger.info("[%s] Authentication method: %s", datetime.now().isoformat(), auth_method)
        
        self.client = AzureContentUnderstandingClient(
            endpoint=self.endpoint,
            api_version="2025-11-01",
            subscription_key=api_key,
            token_provider=token_provider if not api_key else None,
        )
        
        init_duration = time.time() - init_start
        logger.info("[%s] DocumentProcessor initialized in %.2fs", datetime.now().isoformat(), init_duration)
    
    async def extract_content(self, file_bytes: bytes, filename: str) -> str:
        """
        Extract content from a document and return as markdown.
        
        Args:
            file_bytes: The document content as bytes
            filename: The original filename (used to determine file type)
            
        Returns:
            Extracted content as markdown string
        """
        extract_start = time.time()
        logger.info("[%s] Starting content extraction for: %s (%d bytes)", 
                   datetime.now().isoformat(), filename, len(file_bytes))
        
        # Determine content type based on filename extension
        extension = filename.lower().split(".")[-1] if "." in filename else ""
        logger.info("[%s] Detected file extension: %s", datetime.now().isoformat(), extension)
        
        # Handle plain text and markdown files directly
        if extension in ["txt", "md"]:
            logger.info("[%s] Processing as plain text/markdown (no Azure API call needed)", 
                       datetime.now().isoformat())
            content = file_bytes.decode("utf-8")
            duration = time.time() - extract_start
            logger.info("[%s] Text extraction completed in %.2fs (%d chars)", 
                       datetime.now().isoformat(), duration, len(content))
            return content
        
        # Use Azure Content Understanding for other formats (PDF, DOCX, etc.)
        logger.info("[%s] Processing with Azure Content Understanding (format: %s)...", 
                   datetime.now().isoformat(), extension)
        content = self._analyze_document(file_bytes)
        
        duration = time.time() - extract_start
        logger.info("[%s] Document extraction completed in %.2fs (%d chars)", 
                   datetime.now().isoformat(), duration, len(content))
        return content
    
    def _analyze_document(self, file_bytes: bytes) -> str:
        """
        Analyze document using Azure Content Understanding.
        
        Args:
            file_bytes: The document content as bytes
            
        Returns:
            Extracted content as markdown string
        """
        analyze_start = time.time()
        logger.info("[%s] Calling Azure Content Understanding API...", datetime.now().isoformat())
        
        # Use the prebuilt-documentSearch analyzer for document analysis
        # This extracts text, tables, and structure from documents as markdown
        response = self.client.begin_analyze_binary_bytes(analyzer_id = "prebuilt-documentSearch", file_bytes=file_bytes)
        
        logger.info("[%s] Polling for analysis result...", datetime.now().isoformat())
        poll_start = time.time()
        result = self.client.poll_result(response)
        poll_duration = time.time() - poll_start
        logger.info("[%s] Polling completed in %.2fs", datetime.now().isoformat(), poll_duration)

        # Extract markdown from the first content element
        contents = result.get("result", {}).get("contents", [])
        if contents:
            content = contents[0]
            markdown = content.get("markdown", "")
            analyze_duration = time.time() - analyze_start
            logger.info("[%s] Azure Content Understanding analysis completed in %.2fs", 
                       datetime.now().isoformat(), analyze_duration)
            return markdown
        
        logger.warning("[%s] No content extracted from document", datetime.now().isoformat())
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
