"""
Document Processing Service using Azure Content Understanding.

This module handles document processing and extraction using Azure Content Understanding
to convert various document formats to markdown.
"""

import os
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

from .content_understanding_client import AzureContentUnderstandingClient

load_dotenv()


class DocumentProcessor:
    """
    Document processor using Azure Content Understanding.
    
    Processes various document formats and extracts content as markdown.
    """
    
    def __init__(self):
        """Initialize the document processor with Azure credentials."""
        self.endpoint = os.getenv("AZURE_AI_ENDPOINT")
        
        if not self.endpoint:
            raise ValueError(
                "AZURE_AI_ENDPOINT environment variable is required. "
                "Please set it in your .env file."
            )
        
        # Create token provider using DefaultAzureCredential
        def token_provider():
            credential = DefaultAzureCredential()
            token = credential.get_token("https://cognitiveservices.azure.com/.default")
            return token.token
        
        # Check if API key is provided, otherwise use token auth
        api_key = os.getenv("AZURE_AI_API_KEY")
        
        self.client = AzureContentUnderstandingClient(
            endpoint=self.endpoint,
            api_version="2025-11-01",
            subscription_key=api_key,
            token_provider=token_provider if not api_key else None,
        )
    
    async def extract_content(self, file_bytes: bytes, filename: str) -> str:
        """
        Extract content from a document and return as markdown.
        
        Args:
            file_bytes: The document content as bytes
            filename: The original filename (used to determine file type)
            
        Returns:
            Extracted content as markdown string
        """
        # Determine content type based on filename extension
        extension = filename.lower().split(".")[-1] if "." in filename else ""
        
        # Handle plain text and markdown files directly
        if extension in ["txt", "md"]:
            return file_bytes.decode("utf-8")
        
        # Use Azure Content Understanding for other formats (PDF, DOCX, etc.)
        return self._analyze_document(file_bytes)
    
    def _analyze_document(self, file_bytes: bytes) -> str:
        """
        Analyze document using Azure Content Understanding.
        
        Args:
            file_bytes: The document content as bytes
            
        Returns:
            Extracted content as markdown string
        """
        # Use the prebuilt-documentSearch analyzer for document analysis
        # This extracts text, tables, and structure from documents as markdown
        result = self.client.analyze_document(file_bytes, analyzer_id = "prebuilt-documentSearch")
        
        # Extract and return the markdown content
        return self.client.extract_markdown(result)
    
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
