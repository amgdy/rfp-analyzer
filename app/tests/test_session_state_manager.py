"""Tests for services.session_state_manager module."""

import json
import pytest
from unittest.mock import MagicMock, patch


class TestSessionStateManager:
    """Tests for SessionStateManager class."""

    def _make_manager(self, session_id="test-session-123"):
        """Create a SessionStateManager with mocked blob client."""
        with patch("services.session_state_manager.get_blob_storage_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            from services.session_state_manager import SessionStateManager
            mgr = SessionStateManager(session_id)
            return mgr, mock_client

    def test_blob_path(self):
        """Test that blob_path is correct."""
        mgr, _ = self._make_manager("abc123")
        assert mgr.blob_path == "abc123/state.json"

    def test_load_creates_default_state_when_no_blob(self):
        """Test that load() creates default state when blob doesn't exist."""
        mgr, mock_client = self._make_manager()
        mock_client._download_text.return_value = None

        state = mgr.load()

        assert state["version"] == "1.0"
        assert state["session_id"] == "test-session-123"
        assert state["current_step"] == 0
        assert state["uploads"]["rfp"] is None
        assert state["uploads"]["proposals"] == []
        assert state["extraction"]["completed"] is False
        assert state["criteria"]["completed"] is False
        assert state["evaluation"]["completed"] is False
        assert state["reports"]["full_analysis"] is None

    def test_load_parses_existing_state(self):
        """Test that load() parses existing JSON state from blob."""
        mgr, mock_client = self._make_manager()
        existing_state = {
            "version": "1.0",
            "session_id": "test-session-123",
            "current_step": 3,
            "created_at": "2024-01-01T00:00:00+00:00",
            "updated_at": "2024-01-01T01:00:00+00:00",
            "config": {},
            "uploads": {"rfp": {"name": "test.pdf", "size": 1000}, "proposals": []},
            "extraction": {"completed": True},
            "criteria": {"completed": True, "criteria_data": {"criteria": []}},
            "evaluation": {"completed": False},
            "reports": {},
            "step_durations": {},
        }
        mock_client._download_text.return_value = json.dumps(existing_state)

        state = mgr.load()

        assert state["current_step"] == 3
        assert state["uploads"]["rfp"]["name"] == "test.pdf"

    def test_load_handles_corrupt_json(self):
        """Test that load() handles corrupt JSON gracefully."""
        mgr, mock_client = self._make_manager()
        mock_client._download_text.return_value = "not valid json{{"

        state = mgr.load()

        # Should create a fresh default state
        assert state["version"] == "1.0"
        assert state["current_step"] == 0

    def test_save_uploads_to_blob(self):
        """Test that save() serializes state and uploads."""
        mgr, mock_client = self._make_manager()
        mock_client._download_text.return_value = None
        mgr.load()

        mgr.save()

        mock_client._upload_blob.assert_called_once()
        call_args = mock_client._upload_blob.call_args
        assert call_args[0][0] == "test-session-123/state.json"
        # Verify it's valid JSON
        saved_data = json.loads(call_args[0][1].decode("utf-8"))
        assert saved_data["session_id"] == "test-session-123"

    def test_set_step(self):
        """Test step update persists."""
        mgr, mock_client = self._make_manager()
        mock_client._download_text.return_value = None
        mgr.load()

        mgr.set_step(3)

        state = mgr.get_state()
        assert state["current_step"] == 3
        # Should have called save (uploaded)
        assert mock_client._upload_blob.called

    def test_get_step(self):
        """Test getting current step."""
        mgr, mock_client = self._make_manager()
        existing = {"version": "1.0", "current_step": 2, "session_id": "x"}
        mock_client._download_text.return_value = json.dumps(existing)
        mgr.load()

        assert mgr.get_step() == 2

    def test_save_config(self):
        """Test saving configuration."""
        mgr, mock_client = self._make_manager()
        mock_client._download_text.return_value = None
        mgr.load()

        mgr.save_config(
            extraction_service="content_understanding",
            reasoning_effort="high",
            global_criteria="Must be cost-effective",
        )

        state = mgr.get_state()
        assert state["config"]["extraction_service"] == "content_understanding"
        assert state["config"]["reasoning_effort"] == "high"
        assert state["config"]["global_criteria"] == "Must be cost-effective"

    def test_save_upload(self):
        """Test saving upload metadata."""
        mgr, mock_client = self._make_manager()
        mock_client._download_text.return_value = None
        mgr.load()

        rfp = {"name": "rfp.pdf", "size": 5000, "blob_path": "sess/uploads/rfp/rfp.pdf"}
        proposals = [
            {"name": "vendor_a.pdf", "size": 3000, "blob_path": "sess/uploads/proposals/vendor_a.pdf"},
        ]

        mgr.save_upload(rfp=rfp, proposals=proposals)

        state = mgr.get_state()
        assert state["uploads"]["rfp"]["name"] == "rfp.pdf"
        assert len(state["uploads"]["proposals"]) == 1
        assert state["current_step"] >= 1

    def test_save_extraction_complete(self):
        """Test marking extraction as complete."""
        mgr, mock_client = self._make_manager()
        mock_client._download_text.return_value = None
        mgr.load()

        mgr.save_extraction_complete(
            rfp_extracted=True,
            proposals_extracted=["vendor_a.pdf", "vendor_b.pdf"],
            duration_seconds=15.5,
        )

        state = mgr.get_state()
        assert state["extraction"]["completed"] is True
        assert state["extraction"]["rfp_extracted"] is True
        assert state["extraction"]["proposals_extracted"] == ["vendor_a.pdf", "vendor_b.pdf"]
        assert state["extraction"]["duration_seconds"] == 15.5
        assert state["current_step"] >= 2

    def test_save_criteria(self):
        """Test saving criteria data."""
        mgr, mock_client = self._make_manager()
        mock_client._download_text.return_value = None
        mgr.load()

        criteria_data = {
            "rfp_title": "Test RFP",
            "criteria": [{"name": "Cost", "weight": 30}],
        }

        mgr.save_criteria(criteria_data=criteria_data, duration_seconds=8.2)

        state = mgr.get_state()
        assert state["criteria"]["completed"] is True
        assert state["criteria"]["criteria_count"] == 1
        assert state["criteria"]["criteria_data"]["rfp_title"] == "Test RFP"
        assert state["current_step"] >= 3

    def test_save_evaluation(self):
        """Test saving evaluation results."""
        mgr, mock_client = self._make_manager()
        mock_client._download_text.return_value = None
        mgr.load()

        results = [{"supplier_name": "Vendor A", "total_score": 85.0}]
        comparison = {"vendor_rankings": [{"rank": 1, "vendor_name": "Vendor A"}]}

        mgr.save_evaluation(
            results=results,
            comparison=comparison,
            duration_seconds=45.0,
        )

        state = mgr.get_state()
        assert state["evaluation"]["completed"] is True
        assert len(state["evaluation"]["results"]) == 1
        assert state["evaluation"]["comparison"]["vendor_rankings"][0]["rank"] == 1
        assert state["current_step"] >= 4

    def test_save_report(self):
        """Test saving report references."""
        mgr, mock_client = self._make_manager()
        mock_client._download_text.return_value = None
        mgr.load()

        mgr.save_report(
            report_type="full_analysis",
            blob_path="sess/reports/full_analysis_report.docx",
            filename="rfp_full_analysis_report.docx",
        )

        state = mgr.get_state()
        entry = state["reports"]["full_analysis"]
        assert entry["blob_path"] == "sess/reports/full_analysis_report.docx"
        assert entry["filename"] == "rfp_full_analysis_report.docx"
        assert entry["type"] == "full_analysis"
        assert "generated_at" in entry

    def test_save_vendor_report(self):
        """Test saving vendor-specific report references."""
        mgr, mock_client = self._make_manager()
        mock_client._download_text.return_value = None
        mgr.load()

        mgr.save_report(
            report_type="vendor_report",
            blob_path="sess/reports/report_Acme.docx",
            filename="report_Acme.docx",
            vendor_name="Acme Corp",
        )

        state = mgr.get_state()
        vendor_reports = state["reports"]["vendor_reports"]
        assert len(vendor_reports) == 1
        assert vendor_reports[0]["vendor_name"] == "Acme Corp"
        assert vendor_reports[0]["blob_path"] == "sess/reports/report_Acme.docx"

    def test_get_report_blob_paths(self):
        """Test retrieving all report blob paths."""
        mgr, mock_client = self._make_manager()
        mock_client._download_text.return_value = None
        mgr.load()

        # Save multiple reports
        mgr.save_report("full_analysis", "sess/reports/full.docx", "full.docx")
        mgr.save_report("csv_comparison", "sess/reports/comp.csv", "comp.csv")
        mgr.save_report("vendor_report", "sess/reports/v1.docx", "v1.docx", vendor_name="V1")

        paths = mgr.get_report_blob_paths()

        assert "full_analysis" in paths
        assert "csv_comparison" in paths
        assert "vendor_report_V1" in paths
        assert paths["full_analysis"]["blob_path"] == "sess/reports/full.docx"

    def test_save_step_durations(self):
        """Test saving step duration metadata."""
        mgr, mock_client = self._make_manager()
        mock_client._download_text.return_value = None
        mgr.load()

        mgr.save_step_durations({"extraction_total": 12.5, "rfp_processing": 8.0})

        state = mgr.get_state()
        assert state["step_durations"]["extraction_total"] == 12.5
        assert state["step_durations"]["rfp_processing"] == 8.0

    def test_step_never_goes_backwards(self):
        """Test that set_step / save methods never reduce the step number."""
        mgr, mock_client = self._make_manager()
        mock_client._download_text.return_value = None
        mgr.load()

        mgr.set_step(4)
        assert mgr.get_step() == 4

        # save_upload shouldn't reduce step from 4 to 1
        mgr.save_upload(rfp={"name": "x.pdf", "size": 1, "blob_path": "x"})
        assert mgr.get_step() == 4


class TestGetSessionManager:
    """Tests for the module-level helper."""

    def test_returns_manager_instance(self):
        """Test that get_session_manager returns a SessionStateManager."""
        with patch("services.session_state_manager.get_blob_storage_client") as mock_get:
            mock_get.return_value = MagicMock()

            from services.session_state_manager import get_session_manager
            mgr = get_session_manager("test-id")

            assert mgr.session_id == "test-id"
