"""Tests for the telemetry module."""

import os
import pytest
from unittest.mock import patch

from services.telemetry import (
    get_tracer,
    _get_app_version,
    _NoOpTracer,
    _NoOpSpan,
)


class TestGetTracer:
    """Tests for get_tracer()."""

    def test_returns_tracer(self):
        """get_tracer should return a tracer instance."""
        tracer = get_tracer("test_module")
        assert tracer is not None

    def test_noop_tracer_span(self):
        """NoOp tracer should provide a context-manager span."""
        tracer = _NoOpTracer()
        with tracer.start_as_current_span("test") as span:
            span.set_attribute("key", "value")
            span.add_event("event")

    def test_noop_span_exception(self):
        """NoOp span should support record_exception."""
        span = _NoOpSpan()
        span.record_exception(ValueError("test"))
        span.set_status("error")


class TestGetAppVersion:
    """Tests for _get_app_version()."""

    def test_reads_version_from_pyproject(self):
        version = _get_app_version()
        assert version == "0.2.0"


class TestSetupTelemetry:
    """Tests for setup_telemetry()."""

    def test_disabled_via_env(self, monkeypatch):
        """Tracing should be skipped when OTEL_TRACING_ENABLED=false."""
        import services.telemetry as mod

        monkeypatch.setattr(mod, "_telemetry_configured", False)
        monkeypatch.setenv("OTEL_TRACING_ENABLED", "false")
        # Remove any endpoints that might trigger setup
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
        monkeypatch.delenv("APPLICATIONINSIGHTS_CONNECTION_STRING", raising=False)

        result = mod.setup_telemetry()
        assert result is False

    def test_no_exporters_configured(self, monkeypatch):
        """Should return False when no exporters are configured."""
        import services.telemetry as mod

        monkeypatch.setattr(mod, "_telemetry_configured", False)
        monkeypatch.delenv("OTEL_TRACING_ENABLED", raising=False)
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
        monkeypatch.delenv("APPLICATIONINSIGHTS_CONNECTION_STRING", raising=False)

        result = mod.setup_telemetry()
        assert result is False
