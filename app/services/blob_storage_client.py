"""
Azure Blob Storage Client for session-based document storage.

This module provides a client for storing and retrieving documents and
extracted text content in Azure Blob Storage, organized by session ID.

Storage structure:
    <container>/
        <session_id>/
            uploads/
                rfp/<filename>
                proposals/<filename>
            extracted/
                rfp/<filename>.md
                proposals/<filename>.md
"""

import os
from typing import Optional

from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, ContainerClient
from dotenv import load_dotenv

from .logging_config import get_logger

load_dotenv()

logger = get_logger(__name__)

# Default container name for RFP Analyzer sessions
_DEFAULT_CONTAINER_NAME = "rfp-sessions"


class BlobStorageClient:
    """Client for Azure Blob Storage operations scoped to sessions.

    Each session gets a unique folder (prefix) in the blob container.
    Files are organized as:
        <session_id>/uploads/rfp/<filename>
        <session_id>/uploads/proposals/<filename>
        <session_id>/extracted/rfp/<filename>.md
        <session_id>/extracted/proposals/<filename>.md
    """

    def __init__(
        self,
        connection_string: Optional[str] = None,
        account_url: Optional[str] = None,
        container_name: Optional[str] = None,
    ):
        """Initialize the Blob Storage client.

        Args:
            connection_string: Azure Storage connection string (takes priority).
            account_url: Azure Storage account URL (used with DefaultAzureCredential).
            container_name: Container name (defaults to 'rfp-sessions').
        """
        self.container_name = container_name or os.getenv(
            "AZURE_STORAGE_CONTAINER_NAME", _DEFAULT_CONTAINER_NAME
        )

        conn_str = connection_string or os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        acct_url = account_url or os.getenv("AZURE_STORAGE_ACCOUNT_URL")

        if conn_str:
            logger.info("Initializing BlobStorageClient with connection string")
            self._service_client = BlobServiceClient.from_connection_string(conn_str)
        elif acct_url:
            logger.info("Initializing BlobStorageClient with DefaultAzureCredential: %s", acct_url)
            credential = DefaultAzureCredential()
            self._service_client = BlobServiceClient(account_url=acct_url, credential=credential)
        else:
            raise ValueError(
                "Azure Storage configuration is required. "
                "Set AZURE_STORAGE_CONNECTION_STRING or AZURE_STORAGE_ACCOUNT_URL "
                "in your .env file."
            )

        self._container_client: ContainerClient = self._service_client.get_container_client(
            self.container_name
        )
        self._ensure_container_exists()

    def _ensure_container_exists(self):
        """Create the container if it doesn't exist."""
        try:
            self._container_client.get_container_properties()
        except Exception:
            logger.info("Creating blob container: %s", self.container_name)
            self._container_client.create_container()

    # ── Upload operations ──────────────────────────────────────────────────

    def upload_rfp(self, session_id: str, filename: str, file_bytes: bytes) -> str:
        """Upload an RFP file to blob storage.

        Args:
            session_id: The unique session identifier.
            filename: Original filename.
            file_bytes: File content as bytes.

        Returns:
            The blob path where the file was stored.
        """
        blob_path = f"{session_id}/uploads/rfp/{filename}"
        self._upload_blob(blob_path, file_bytes)
        logger.info("Uploaded RFP to blob: %s (%d bytes)", blob_path, len(file_bytes))
        return blob_path

    def upload_proposal(self, session_id: str, filename: str, file_bytes: bytes) -> str:
        """Upload a proposal file to blob storage.

        Args:
            session_id: The unique session identifier.
            filename: Original filename.
            file_bytes: File content as bytes.

        Returns:
            The blob path where the file was stored.
        """
        blob_path = f"{session_id}/uploads/proposals/{filename}"
        self._upload_blob(blob_path, file_bytes)
        logger.info("Uploaded proposal to blob: %s (%d bytes)", blob_path, len(file_bytes))
        return blob_path

    # ── Extracted content operations ───────────────────────────────────────

    def store_extracted_rfp(self, session_id: str, filename: str, content: str) -> str:
        """Store extracted RFP text content in blob storage.

        Args:
            session_id: The unique session identifier.
            filename: Original filename (used to derive the blob name).
            content: Extracted markdown text.

        Returns:
            The blob path where the content was stored.
        """
        blob_path = f"{session_id}/extracted/rfp/{filename}.md"
        self._upload_blob(blob_path, content.encode("utf-8"))
        logger.info("Stored extracted RFP content: %s (%d chars)", blob_path, len(content))
        return blob_path

    def store_extracted_proposal(self, session_id: str, filename: str, content: str) -> str:
        """Store extracted proposal text content in blob storage.

        Args:
            session_id: The unique session identifier.
            filename: Original filename (used to derive the blob name).
            content: Extracted markdown text.

        Returns:
            The blob path where the content was stored.
        """
        blob_path = f"{session_id}/extracted/proposals/{filename}.md"
        self._upload_blob(blob_path, content.encode("utf-8"))
        logger.info("Stored extracted proposal content: %s (%d chars)", blob_path, len(content))
        return blob_path

    def get_extracted_rfp(self, session_id: str, filename: str) -> Optional[str]:
        """Retrieve extracted RFP content from blob storage.

        Args:
            session_id: The unique session identifier.
            filename: Original filename.

        Returns:
            The extracted text content, or None if not found.
        """
        blob_path = f"{session_id}/extracted/rfp/{filename}.md"
        return self._download_text(blob_path)

    def get_extracted_proposal(self, session_id: str, filename: str) -> Optional[str]:
        """Retrieve extracted proposal content from blob storage.

        Args:
            session_id: The unique session identifier.
            filename: Original filename.

        Returns:
            The extracted text content, or None if not found.
        """
        blob_path = f"{session_id}/extracted/proposals/{filename}.md"
        return self._download_text(blob_path)

    # ── File download operations ───────────────────────────────────────────

    def download_rfp(self, session_id: str, filename: str) -> Optional[bytes]:
        """Download an uploaded RFP file from blob storage.

        Args:
            session_id: The unique session identifier.
            filename: Original filename.

        Returns:
            File content as bytes, or None if not found.
        """
        blob_path = f"{session_id}/uploads/rfp/{filename}"
        return self._download_blob(blob_path)

    def download_proposal(self, session_id: str, filename: str) -> Optional[bytes]:
        """Download an uploaded proposal file from blob storage.

        Args:
            session_id: The unique session identifier.
            filename: Original filename.

        Returns:
            File content as bytes, or None if not found.
        """
        blob_path = f"{session_id}/uploads/proposals/{filename}"
        return self._download_blob(blob_path)

    # ── List operations ────────────────────────────────────────────────────

    def list_proposals(self, session_id: str) -> list[str]:
        """List all uploaded proposal filenames for a session.

        Args:
            session_id: The unique session identifier.

        Returns:
            List of proposal filenames.
        """
        prefix = f"{session_id}/uploads/proposals/"
        blobs = self._container_client.list_blobs(name_starts_with=prefix)
        return [blob.name.removeprefix(prefix) for blob in blobs]

    def session_exists(self, session_id: str) -> bool:
        """Check if a session exists in blob storage.

        Args:
            session_id: The unique session identifier.

        Returns:
            True if any blobs exist for this session.
        """
        prefix = f"{session_id}/"
        blobs = self._container_client.list_blobs(name_starts_with=prefix, results_per_page=1)
        return any(True for _ in blobs)

    # ── Internal helpers ───────────────────────────────────────────────────

    def _upload_blob(self, blob_path: str, data: bytes) -> None:
        """Upload data to a blob, overwriting if exists."""
        blob_client = self._container_client.get_blob_client(blob_path)
        blob_client.upload_blob(data, overwrite=True)

    def _download_blob(self, blob_path: str) -> Optional[bytes]:
        """Download blob content as bytes. Returns None if not found."""
        blob_client = self._container_client.get_blob_client(blob_path)
        try:
            download = blob_client.download_blob()
            return download.readall()
        except Exception:
            logger.debug("Blob not found: %s", blob_path)
            return None

    def _download_text(self, blob_path: str) -> Optional[str]:
        """Download blob content as UTF-8 text. Returns None if not found."""
        data = self._download_blob(blob_path)
        if data is not None:
            return data.decode("utf-8")
        return None


# ── Module-level singleton ─────────────────────────────────────────────────

_client_instance: Optional[BlobStorageClient] = None


def get_blob_storage_client() -> BlobStorageClient:
    """Get or create the singleton BlobStorageClient instance.

    Returns:
        The shared BlobStorageClient instance.

    Raises:
        ValueError: If storage configuration is missing.
    """
    global _client_instance
    if _client_instance is None:
        _client_instance = BlobStorageClient()
    return _client_instance
