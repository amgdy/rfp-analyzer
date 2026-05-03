"""
Session State Manager for persisting workflow state to Azure Blob Storage.

This module manages a JSON state file per session that tracks:
- Current workflow step
- Uploaded file metadata
- Extracted content references
- Evaluation results
- Generated report blob paths with permanent download links

State file location: <session_id>/state.json

The state file enables:
1. Resuming from any step after page reload or session loss
2. Permanent shareable links to generated reports (via time-limited SAS tokens)
3. Full session audit trail
"""

import json
from datetime import datetime, timezone
from typing import Any, Optional

from .blob_storage_client import get_blob_storage_client
from .logging_config import get_logger

logger = get_logger(__name__)

# Schema version for forward compatibility
_STATE_VERSION = "1.0"

# State file path within session folder
_STATE_BLOB_NAME = "state.json"


def _now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _default_state(session_id: str) -> dict:
    """Create a fresh default session state."""
    return {
        "version": _STATE_VERSION,
        "session_id": session_id,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "current_step": 0,
        "config": {
            "extraction_service": "document_intelligence",
            "reasoning_effort": "low",
            "global_criteria": "",
        },
        "uploads": {
            "rfp": None,  # {"name": str, "size": int, "blob_path": str}
            "proposals": [],  # [{"name": str, "size": int, "blob_path": str}]
        },
        "extraction": {
            "completed": False,
            "rfp_extracted": False,
            "proposals_extracted": [],  # list of filenames with extracted content
            "duration_seconds": None,
        },
        "criteria": {
            "completed": False,
            "criteria_count": 0,
            "criteria_data": None,  # The full extracted criteria dict
            "duration_seconds": None,
        },
        "evaluation": {
            "completed": False,
            "results": [],  # Full evaluation results per vendor
            "disqualified": [],  # Disqualified proposals
            "comparison": None,  # Comparison results
            "duration_seconds": None,
        },
        "reports": {
            # Each entry: {"blob_path": str, "filename": str, "generated_at": str, "type": str}
            "full_analysis": None,
            "csv_comparison": None,
            "json_data": None,
            "vendor_reports": [],  # [{"vendor_name": str, "blob_path": str, ...}]
        },
        "step_durations": {},
    }


class SessionStateManager:
    """Manages persistent session state in Azure Blob Storage.

    The state is stored as a JSON file at <session_id>/state.json and contains
    all metadata needed to resume a session from any step.
    """

    def __init__(self, session_id: str):
        """Initialize the session state manager.

        Args:
            session_id: The unique session identifier.
        """
        self.session_id = session_id
        self._client = get_blob_storage_client()
        self._state: Optional[dict] = None

    @property
    def blob_path(self) -> str:
        """The blob path for this session's state file."""
        return f"{self.session_id}/{_STATE_BLOB_NAME}"

    def load(self) -> dict:
        """Load session state from blob storage.

        Creates a new default state if none exists.

        Returns:
            The session state dictionary.
        """
        data = self._client._download_text(self.blob_path)
        if data:
            try:
                self._state = json.loads(data)
                logger.debug("Loaded session state: %s (step %d)",
                             self.session_id, self._state.get("current_step", 0))
            except json.JSONDecodeError:
                logger.warning("Corrupt state file for session %s, creating new state",
                               self.session_id)
                self._state = _default_state(self.session_id)
        else:
            self._state = _default_state(self.session_id)
        return self._state

    def save(self) -> None:
        """Persist current state to blob storage."""
        if self._state is None:
            return
        self._state["updated_at"] = _now_iso()
        data = json.dumps(self._state, indent=2, ensure_ascii=False, default=str)
        self._client._upload_blob(self.blob_path, data.encode("utf-8"))
        logger.debug("Saved session state: %s (step %d)",
                     self.session_id, self._state.get("current_step", 0))

    def get_state(self) -> dict:
        """Get the current state (loads from blob if not yet loaded).

        Returns:
            The session state dictionary.
        """
        if self._state is None:
            self.load()
        return self._state

    # ── Step tracking ──────────────────────────────────────────────────────

    def set_step(self, step: int) -> None:
        """Update the current workflow step.

        Args:
            step: Step number (0=landing, 1=upload, 2=extract, 3=criteria, 4=score).
        """
        state = self.get_state()
        state["current_step"] = step
        self.save()

    def get_step(self) -> int:
        """Get the current workflow step.

        Returns:
            The current step number.
        """
        return self.get_state().get("current_step", 0)

    # ── Config ─────────────────────────────────────────────────────────────

    def save_config(
        self,
        extraction_service: str = "",
        reasoning_effort: str = "",
        global_criteria: str = "",
    ) -> None:
        """Save workflow configuration.

        Args:
            extraction_service: The extraction service name.
            reasoning_effort: Reasoning effort level.
            global_criteria: User-supplied global criteria text.
        """
        state = self.get_state()
        if extraction_service:
            state["config"]["extraction_service"] = extraction_service
        if reasoning_effort:
            state["config"]["reasoning_effort"] = reasoning_effort
        state["config"]["global_criteria"] = global_criteria
        self.save()

    # ── Uploads ────────────────────────────────────────────────────────────

    def save_upload(
        self,
        rfp: Optional[dict] = None,
        proposals: Optional[list] = None,
    ) -> None:
        """Save upload metadata.

        Args:
            rfp: RFP file metadata {"name": str, "size": int, "blob_path": str}.
            proposals: List of proposal metadata dicts.
        """
        state = self.get_state()
        if rfp is not None:
            state["uploads"]["rfp"] = rfp
        if proposals is not None:
            state["uploads"]["proposals"] = proposals
        state["current_step"] = max(state["current_step"], 1)
        self.save()

    # ── Extraction ─────────────────────────────────────────────────────────

    def save_extraction_complete(
        self,
        rfp_extracted: bool = True,
        proposals_extracted: Optional[list] = None,
        duration_seconds: Optional[float] = None,
    ) -> None:
        """Mark extraction as complete.

        Args:
            rfp_extracted: Whether RFP extraction succeeded.
            proposals_extracted: List of proposal filenames that were extracted.
            duration_seconds: Total extraction duration.
        """
        state = self.get_state()
        state["extraction"]["completed"] = True
        state["extraction"]["rfp_extracted"] = rfp_extracted
        if proposals_extracted:
            state["extraction"]["proposals_extracted"] = proposals_extracted
        if duration_seconds is not None:
            state["extraction"]["duration_seconds"] = duration_seconds
        state["current_step"] = max(state["current_step"], 2)
        self.save()

    # ── Criteria ───────────────────────────────────────────────────────────

    def save_criteria(
        self,
        criteria_data: dict,
        duration_seconds: Optional[float] = None,
    ) -> None:
        """Save extracted criteria.

        Args:
            criteria_data: The full criteria extraction dict.
            duration_seconds: Extraction duration.
        """
        state = self.get_state()
        state["criteria"]["completed"] = True
        state["criteria"]["criteria_count"] = len(criteria_data.get("criteria", []))
        state["criteria"]["criteria_data"] = criteria_data
        if duration_seconds is not None:
            state["criteria"]["duration_seconds"] = duration_seconds
        state["current_step"] = max(state["current_step"], 3)
        self.save()

    # ── Evaluation ─────────────────────────────────────────────────────────

    def save_evaluation(
        self,
        results: list,
        disqualified: Optional[list] = None,
        comparison: Optional[dict] = None,
        duration_seconds: Optional[float] = None,
    ) -> None:
        """Save evaluation results.

        Args:
            results: List of qualified evaluation result dicts.
            disqualified: List of disqualified evaluation results.
            comparison: Comparison results dict.
            duration_seconds: Total evaluation duration.
        """
        state = self.get_state()
        state["evaluation"]["completed"] = True
        state["evaluation"]["results"] = results
        state["evaluation"]["disqualified"] = disqualified or []
        state["evaluation"]["comparison"] = comparison
        if duration_seconds is not None:
            state["evaluation"]["duration_seconds"] = duration_seconds
        state["current_step"] = max(state["current_step"], 4)
        self.save()

    # ── Reports ────────────────────────────────────────────────────────────

    def save_report(
        self,
        report_type: str,
        blob_path: str,
        filename: str,
        vendor_name: Optional[str] = None,
    ) -> None:
        """Save a generated report reference.

        Args:
            report_type: One of 'full_analysis', 'csv_comparison', 'json_data', 'vendor_report'.
            blob_path: The blob path where the report is stored.
            filename: The download filename.
            vendor_name: Vendor name (for vendor_report type only).
        """
        state = self.get_state()
        report_entry = {
            "blob_path": blob_path,
            "filename": filename,
            "generated_at": _now_iso(),
            "type": report_type,
        }

        if report_type == "vendor_report":
            report_entry["vendor_name"] = vendor_name or "Unknown"
            state["reports"]["vendor_reports"].append(report_entry)
        else:
            state["reports"][report_type] = report_entry

        self.save()

    def get_report_blob_paths(self) -> dict:
        """Get all report blob paths for download link generation.

        Returns:
            Dict mapping report type/name to blob_path.
        """
        state = self.get_state()
        reports = state.get("reports", {})
        paths = {}

        for rtype in ("full_analysis", "csv_comparison", "json_data"):
            entry = reports.get(rtype)
            if entry and entry.get("blob_path"):
                paths[rtype] = entry

        for vr in reports.get("vendor_reports", []):
            if vr.get("blob_path"):
                key = f"vendor_report_{vr.get('vendor_name', 'unknown')}"
                paths[key] = vr

        return paths

    # ── Step durations ─────────────────────────────────────────────────────

    def save_step_durations(self, durations: dict) -> None:
        """Save step duration metadata.

        Args:
            durations: Dict of step_name -> duration_seconds.
        """
        state = self.get_state()
        state["step_durations"].update(durations)
        self.save()


# ── Module-level helper ────────────────────────────────────────────────────


def get_session_manager(session_id: str) -> SessionStateManager:
    """Create a SessionStateManager for the given session.

    Args:
        session_id: The unique session identifier.

    Returns:
        A SessionStateManager instance.
    """
    return SessionStateManager(session_id)
