"""Tests for services.blob_storage_client module."""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock


class TestBlobStorageClient:
    """Tests for BlobStorageClient class."""

    def _make_client(self, mock_service_client=None):
        """Create a BlobStorageClient with mocked Azure SDK."""
        with patch.dict("os.environ", {
            "AZURE_STORAGE_CONNECTION_STRING": "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=dGVzdA==;EndpointSuffix=core.windows.net"
        }):
            with patch("services.blob_storage_client.BlobServiceClient") as mock_bsc:
                mock_svc = mock_service_client or MagicMock()
                mock_bsc.from_connection_string.return_value = mock_svc
                mock_container = MagicMock()
                mock_svc.get_container_client.return_value = mock_container

                from services.blob_storage_client import BlobStorageClient
                # Reset singleton
                import services.blob_storage_client as mod
                mod._client_instance = None

                client = BlobStorageClient(
                    connection_string="DefaultEndpointsProtocol=https;AccountName=test;AccountKey=dGVzdA==;EndpointSuffix=core.windows.net"
                )
                return client, mock_container

    def test_init_with_connection_string(self):
        """Test initialization with connection string."""
        client, mock_container = self._make_client()
        assert client.container_name == "rfp-sessions"

    def test_init_with_custom_container_name(self):
        """Test initialization with custom container name."""
        with patch.dict("os.environ", {
            "AZURE_STORAGE_CONNECTION_STRING": "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=dGVzdA==;EndpointSuffix=core.windows.net",
            "AZURE_STORAGE_CONTAINER_NAME": "custom-container",
        }):
            with patch("services.blob_storage_client.BlobServiceClient") as mock_bsc:
                mock_svc = MagicMock()
                mock_bsc.from_connection_string.return_value = mock_svc
                mock_svc.get_container_client.return_value = MagicMock()

                from services.blob_storage_client import BlobStorageClient
                client = BlobStorageClient(
                    connection_string="DefaultEndpointsProtocol=https;AccountName=test;AccountKey=dGVzdA==;EndpointSuffix=core.windows.net",
                    container_name="custom-container",
                )
                assert client.container_name == "custom-container"

    def test_init_raises_without_config(self):
        """Test that initialization fails without storage config."""
        with patch.dict("os.environ", {}, clear=True):
            # Remove env vars that would allow initialization
            import os
            env_backup = {}
            for key in ["AZURE_STORAGE_CONNECTION_STRING", "AZURE_STORAGE_ACCOUNT_URL"]:
                if key in os.environ:
                    env_backup[key] = os.environ.pop(key)

            try:
                from services.blob_storage_client import BlobStorageClient
                with pytest.raises(ValueError, match="Azure Storage configuration is required"):
                    BlobStorageClient(connection_string=None, account_url=None)
            finally:
                os.environ.update(env_backup)

    def test_upload_rfp(self):
        """Test uploading an RFP file."""
        client, mock_container = self._make_client()
        mock_blob = MagicMock()
        mock_container.get_blob_client.return_value = mock_blob

        result = client.upload_rfp("session123", "test.pdf", b"pdf-content")

        assert result == "session123/uploads/rfp/test.pdf"
        mock_container.get_blob_client.assert_called_with("session123/uploads/rfp/test.pdf")
        mock_blob.upload_blob.assert_called_once_with(b"pdf-content", overwrite=True)

    def test_upload_proposal(self):
        """Test uploading a proposal file."""
        client, mock_container = self._make_client()
        mock_blob = MagicMock()
        mock_container.get_blob_client.return_value = mock_blob

        result = client.upload_proposal("session123", "vendor_a.pdf", b"proposal-content")

        assert result == "session123/uploads/proposals/vendor_a.pdf"
        mock_container.get_blob_client.assert_called_with("session123/uploads/proposals/vendor_a.pdf")
        mock_blob.upload_blob.assert_called_once_with(b"proposal-content", overwrite=True)

    def test_store_extracted_rfp(self):
        """Test storing extracted RFP content."""
        client, mock_container = self._make_client()
        mock_blob = MagicMock()
        mock_container.get_blob_client.return_value = mock_blob

        result = client.store_extracted_rfp("session123", "test.pdf", "# RFP Content")

        assert result == "session123/extracted/rfp/test.pdf.md"
        mock_blob.upload_blob.assert_called_once_with(b"# RFP Content", overwrite=True)

    def test_store_extracted_proposal(self):
        """Test storing extracted proposal content."""
        client, mock_container = self._make_client()
        mock_blob = MagicMock()
        mock_container.get_blob_client.return_value = mock_blob

        result = client.store_extracted_proposal("session123", "vendor_a.pdf", "# Proposal")

        assert result == "session123/extracted/proposals/vendor_a.pdf.md"
        mock_blob.upload_blob.assert_called_once_with(b"# Proposal", overwrite=True)

    def test_get_extracted_rfp_found(self):
        """Test retrieving extracted RFP content."""
        client, mock_container = self._make_client()
        mock_blob = MagicMock()
        mock_container.get_blob_client.return_value = mock_blob
        mock_download = MagicMock()
        mock_download.readall.return_value = b"# RFP Content"
        mock_blob.download_blob.return_value = mock_download

        result = client.get_extracted_rfp("session123", "test.pdf")

        assert result == "# RFP Content"
        mock_container.get_blob_client.assert_called_with("session123/extracted/rfp/test.pdf.md")

    def test_get_extracted_rfp_not_found(self):
        """Test retrieving non-existent extracted RFP content."""
        client, mock_container = self._make_client()
        mock_blob = MagicMock()
        mock_container.get_blob_client.return_value = mock_blob
        mock_blob.download_blob.side_effect = Exception("BlobNotFound")

        result = client.get_extracted_rfp("session123", "missing.pdf")

        assert result is None

    def test_get_extracted_proposal_found(self):
        """Test retrieving extracted proposal content."""
        client, mock_container = self._make_client()
        mock_blob = MagicMock()
        mock_container.get_blob_client.return_value = mock_blob
        mock_download = MagicMock()
        mock_download.readall.return_value = b"# Proposal Content"
        mock_blob.download_blob.return_value = mock_download

        result = client.get_extracted_proposal("session123", "vendor.pdf")

        assert result == "# Proposal Content"

    def test_download_rfp(self):
        """Test downloading an uploaded RFP file."""
        client, mock_container = self._make_client()
        mock_blob = MagicMock()
        mock_container.get_blob_client.return_value = mock_blob
        mock_download = MagicMock()
        mock_download.readall.return_value = b"raw-pdf-bytes"
        mock_blob.download_blob.return_value = mock_download

        result = client.download_rfp("session123", "test.pdf")

        assert result == b"raw-pdf-bytes"
        mock_container.get_blob_client.assert_called_with("session123/uploads/rfp/test.pdf")

    def test_download_proposal(self):
        """Test downloading an uploaded proposal file."""
        client, mock_container = self._make_client()
        mock_blob = MagicMock()
        mock_container.get_blob_client.return_value = mock_blob
        mock_download = MagicMock()
        mock_download.readall.return_value = b"raw-proposal-bytes"
        mock_blob.download_blob.return_value = mock_download

        result = client.download_proposal("session123", "vendor.pdf")

        assert result == b"raw-proposal-bytes"

    def test_download_rfp_not_found(self):
        """Test downloading non-existent RFP returns None."""
        client, mock_container = self._make_client()
        mock_blob = MagicMock()
        mock_container.get_blob_client.return_value = mock_blob
        mock_blob.download_blob.side_effect = Exception("BlobNotFound")

        result = client.download_rfp("session123", "missing.pdf")

        assert result is None

    def test_list_proposals(self):
        """Test listing proposal files for a session."""
        client, mock_container = self._make_client()

        mock_blob1 = MagicMock()
        mock_blob1.name = "session123/uploads/proposals/vendor_a.pdf"
        mock_blob2 = MagicMock()
        mock_blob2.name = "session123/uploads/proposals/vendor_b.pdf"
        mock_container.list_blobs.return_value = [mock_blob1, mock_blob2]

        result = client.list_proposals("session123")

        assert result == ["vendor_a.pdf", "vendor_b.pdf"]
        mock_container.list_blobs.assert_called_with(
            name_starts_with="session123/uploads/proposals/"
        )

    def test_session_exists_true(self):
        """Test session_exists returns True when blobs exist."""
        client, mock_container = self._make_client()
        mock_blob = MagicMock()
        mock_blob.name = "session123/uploads/rfp/test.pdf"
        mock_container.list_blobs.return_value = iter([mock_blob])

        result = client.session_exists("session123")

        assert result is True

    def test_session_exists_false(self):
        """Test session_exists returns False when no blobs exist."""
        client, mock_container = self._make_client()
        mock_container.list_blobs.return_value = iter([])

        result = client.session_exists("nonexistent")

        assert result is False


class TestGetBlobStorageClient:
    """Tests for the module-level singleton accessor."""

    def test_get_blob_storage_client_raises_without_config(self):
        """Test that get_blob_storage_client raises when no config is available."""
        import services.blob_storage_client as mod
        mod._client_instance = None

        with patch.dict("os.environ", {}, clear=True):
            import os
            env_backup = {}
            for key in ["AZURE_STORAGE_CONNECTION_STRING", "AZURE_STORAGE_ACCOUNT_URL"]:
                if key in os.environ:
                    env_backup[key] = os.environ.pop(key)

            try:
                with pytest.raises(ValueError):
                    mod.get_blob_storage_client()
            finally:
                os.environ.update(env_backup)
                mod._client_instance = None

    def test_get_blob_storage_client_singleton(self):
        """Test that get_blob_storage_client returns the same instance."""
        import services.blob_storage_client as mod

        mock_client = MagicMock()
        mod._client_instance = mock_client

        result = mod.get_blob_storage_client()
        assert result is mock_client

        # Cleanup
        mod._client_instance = None


class TestBlobPathGeneration:
    """Tests for correct blob path generation."""

    def test_rfp_upload_path(self):
        """Test RFP upload path format."""
        client, mock_container = TestBlobStorageClient()._make_client()
        mock_container.get_blob_client.return_value = MagicMock()

        path = client.upload_rfp("abc123", "document.pdf", b"data")
        assert path == "abc123/uploads/rfp/document.pdf"

    def test_proposal_upload_path(self):
        """Test proposal upload path format."""
        client, mock_container = TestBlobStorageClient()._make_client()
        mock_container.get_blob_client.return_value = MagicMock()

        path = client.upload_proposal("abc123", "vendor.docx", b"data")
        assert path == "abc123/uploads/proposals/vendor.docx"

    def test_extracted_rfp_path(self):
        """Test extracted RFP content path format."""
        client, mock_container = TestBlobStorageClient()._make_client()
        mock_container.get_blob_client.return_value = MagicMock()

        path = client.store_extracted_rfp("abc123", "doc.pdf", "content")
        assert path == "abc123/extracted/rfp/doc.pdf.md"

    def test_extracted_proposal_path(self):
        """Test extracted proposal content path format."""
        client, mock_container = TestBlobStorageClient()._make_client()
        mock_container.get_blob_client.return_value = MagicMock()

        path = client.store_extracted_proposal("abc123", "vendor.pdf", "content")
        assert path == "abc123/extracted/proposals/vendor.pdf.md"

    def test_special_characters_in_filename(self):
        """Test that filenames with special characters are handled."""
        client, mock_container = TestBlobStorageClient()._make_client()
        mock_container.get_blob_client.return_value = MagicMock()

        path = client.upload_rfp("sess1", "My Document (v2).pdf", b"data")
        assert path == "sess1/uploads/rfp/My Document (v2).pdf"
