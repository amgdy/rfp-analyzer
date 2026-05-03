"""Download handler for session reports with time-limited SAS URLs.

This module provides a Streamlit page that generates temporary download
links for reports stored in Azure Blob Storage. Pass a session ID and
optional report type to get a time-limited SAS-signed URL.

Usage:
    ?session=<session_id>&download=<report_type>

Report types:
    - full_analysis: Full analysis Word document
    - csv_comparison: CSV comparison report
    - json_data: Full evaluation data as JSON
    - vendor_report_<vendor_name>: Individual vendor Word report
"""

import streamlit as st

from services.blob_storage_client import get_blob_storage_client, is_valid_session_id
from services.session_state_manager import get_session_manager
from services.logging_config import get_logger

logger = get_logger(__name__)

# SAS URL expiry time in minutes
_SAS_EXPIRY_MINUTES = 60


def render_download_page():
    """Render the download handler page.

    Reads 'session' and 'download' from query params and generates
    a time-limited SAS URL for the requested report.
    """
    session_id = st.query_params.get("session")
    report_type = st.query_params.get("download")

    if not session_id:
        st.error("❌ No session ID provided. Add `?session=<id>` to the URL.")
        return

    # Validate session ID format (alphanumeric, 8-32 chars)
    if not is_valid_session_id(session_id):
        st.error("❌ Invalid session ID format.")
        return

    if not report_type:
        # Show all available reports for this session
        _render_report_list(session_id)
        return

    # Generate download URL for the specific report
    _generate_download_link(session_id, report_type)


def _render_report_list(session_id: str):
    """Show all available reports for a session with download links."""
    st.header("📥 Session Reports")
    st.caption(f"Session: `{session_id}`")

    try:
        mgr = get_session_manager(session_id)
        state = mgr.load()

        if state.get("current_step", 0) < 4:
            st.warning("⚠️ This session has not completed evaluation yet. No reports available.")
            return

        reports = state.get("reports", {})
        has_reports = False

        # Full analysis report
        if reports.get("full_analysis"):
            has_reports = True
            entry = reports["full_analysis"]
            st.markdown("### 📑 Full Analysis Report")
            st.markdown(f"Generated: {entry.get('generated_at', 'Unknown')}")
            _download_button(session_id, "full_analysis", entry)

        # CSV comparison
        if reports.get("csv_comparison"):
            has_reports = True
            entry = reports["csv_comparison"]
            st.markdown("### 📊 CSV Comparison")
            st.markdown(f"Generated: {entry.get('generated_at', 'Unknown')}")
            _download_button(session_id, "csv_comparison", entry)

        # JSON data
        if reports.get("json_data"):
            has_reports = True
            entry = reports["json_data"]
            st.markdown("### 📋 Evaluation Data (JSON)")
            st.markdown(f"Generated: {entry.get('generated_at', 'Unknown')}")
            _download_button(session_id, "json_data", entry)

        # Vendor reports
        vendor_reports = reports.get("vendor_reports", [])
        if vendor_reports:
            has_reports = True
            st.markdown("### 📄 Individual Vendor Reports")
            for vr in vendor_reports:
                vendor_name = vr.get("vendor_name", "Unknown")
                st.markdown(f"**{vendor_name}** — Generated: {vr.get('generated_at', 'Unknown')}")
                report_key = f"vendor_report_{vendor_name}"
                _download_button(session_id, report_key, vr)

        if not has_reports:
            st.info("No reports have been generated for this session yet.")

    except Exception as e:
        logger.error("Failed to load session reports: %s", str(e))
        st.error(f"❌ Failed to load session reports: {e}")


def _download_button(session_id: str, report_type: str, entry: dict):
    """Render a download link/button for a report entry."""
    try:
        client = get_blob_storage_client()
        blob_path = entry.get("blob_path", "")
        filename = entry.get("filename", "report")

        url = client.generate_download_url(
            blob_path,
            expiry_minutes=_SAS_EXPIRY_MINUTES,
            filename=filename,
        )

        if url:
            st.link_button(
                f"⬇️ Download {filename}",
                url,
                use_container_width=True,
            )
            st.caption(f"Link valid for {_SAS_EXPIRY_MINUTES} minutes")
        else:
            st.warning(f"Could not generate download link for {filename}")

    except Exception as e:
        st.error(f"Error generating download link: {e}")


def _generate_download_link(session_id: str, report_type: str):
    """Generate and display a download link for a specific report."""
    st.header("📥 Report Download")
    st.caption(f"Session: `{session_id}` | Report: `{report_type}`")

    try:
        mgr = get_session_manager(session_id)
        state = mgr.load()
        reports = state.get("reports", {})

        # Find the report entry
        entry = None
        if report_type.startswith("vendor_report_"):
            vendor_name = report_type.removeprefix("vendor_report_")
            for vr in reports.get("vendor_reports", []):
                if vr.get("vendor_name") == vendor_name:
                    entry = vr
                    break
        else:
            entry = reports.get(report_type)

        if not entry:
            st.error(f"❌ Report '{report_type}' not found for this session.")
            st.info("Available reports:")
            _render_report_list(session_id)
            return

        _download_button(session_id, report_type, entry)

    except Exception as e:
        logger.error("Failed to generate download link: %s", str(e))
        st.error(f"❌ Error: {e}")
