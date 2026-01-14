"""
Document Processing Service using Azure Content Understanding.

This module handles document processing and extraction using Azure Content Understanding
to convert various document formats to markdown.
"""

import os
import logging
import time
import uuid
from datetime import datetime
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
        logger.info("Initializing DocumentProcessor...")
        init_start = time.time()
        
        self.endpoint = os.getenv("AZURE_AI_ENDPOINT")
        
        if not self.endpoint:
            raise ValueError(
                "AZURE_AI_ENDPOINT environment variable is required. "
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
        
        self.client = AzureContentUnderstandingClient(
            endpoint=self.endpoint,
            api_version="2025-11-01",
            subscription_key=api_key,
            token_provider=token_provider if not api_key else None,
        )
        
        init_duration = time.time() - init_start
        logger.info("DocumentProcessor initialized in %.2fs", init_duration)
    
    async def extract_content(self, file_bytes: bytes, filename: str) -> str:
        """
        Extract content from a document and return as markdown.
        
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
        logger.info("[REQ:%s] Starting content extraction for: %s (%d bytes)", 
                   request_id, filename, len(file_bytes))
        
        # Determine content type based on filename extension
        extension = filename.lower().split(".")[-1] if "." in filename else ""
        logger.info("[REQ:%s] Detected file extension: %s", request_id, extension)
        
        # Handle plain text and markdown files directly
        if extension in ["txt", "md"]:
            logger.info("[REQ:%s] Processing as plain text/markdown (no Azure API call needed)", request_id)
            content = file_bytes.decode("utf-8")
            duration = time.time() - extract_start
            logger.info("[REQ:%s] Text extraction completed in %.3fs (%d chars)", 
                       request_id, duration, len(content))
            return content
        
        # Use Azure Content Understanding for other formats (PDF, DOCX, etc.)
        # Run the blocking API call in a thread pool to enable true parallelism
        logger.info("[REQ:%s] Processing with Azure Content Understanding (format: %s)...", 
                   request_id, extension)
        content = await asyncio.to_thread(self._analyze_document, file_bytes, request_id)
        
        duration = time.time() - extract_start
        logger.info("[REQ:%s] ✅ Document extraction completed in %.3fs (%d chars)", 
                   request_id, duration, len(content))
        return content
    
    def _analyze_document(self, file_bytes: bytes, request_id: str = "unknown") -> str:
        """
        Analyze document using Azure Content Understanding.
        
        Args:
            file_bytes: The document content as bytes
            request_id: Unique request ID for logging correlation
            
        Returns:
            Extracted content as markdown string
        """
        analyze_start = time.time()
        logger.info("[REQ:%s] 📤 Calling Azure Content Understanding API...", request_id)
        
        # Use the prebuilt-documentSearch analyzer for document analysis
        # This extracts text, tables, and structure from documents as markdown
        api_call_start = time.time()
        response = self.client.begin_analyze_binary_bytes(analyzer_id="prebuilt-documentSearch", file_bytes=file_bytes)
        api_call_duration = time.time() - api_call_start
        logger.info("[REQ:%s] API call initiated in %.3fs", request_id, api_call_duration)
        
        logger.info("[REQ:%s] ⏳ Polling for analysis result...", request_id)
        poll_start = time.time()
        result = self.client.poll_result(response)
        poll_duration = time.time() - poll_start
        logger.info("[REQ:%s] ✅ Polling completed in %.3fs", request_id, poll_duration)

        # Extract markdown from the first content element
        parse_start = time.time()
        contents = result.get("result", {}).get("contents", [])
        if contents:
            content = contents[0]
            markdown = content.get("markdown", "")
            parse_duration = time.time() - parse_start
            analyze_duration = time.time() - analyze_start
            logger.info("[REQ:%s] Azure Content Understanding analysis completed:", request_id)
            logger.info("[REQ:%s]   - API initiation: %.3fs", request_id, api_call_duration)
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
