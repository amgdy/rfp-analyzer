"""
OpenTelemetry Tracing & Observability Setup for RFP Analyzer.

This module configures distributed tracing using OpenTelemetry with support for:
- Console exporter (development / Aspire Dashboard)
- OTLP exporter (Aspire Dashboard, Jaeger, etc.)
- Azure Monitor exporter (Application Insights)
- Agent Framework auto-instrumentation

Usage:
    from services.telemetry import setup_telemetry, get_tracer

    # Call once at application startup (in main.py)
    setup_telemetry()

    # Get a tracer in any module
    tracer = get_tracer(__name__)
    with tracer.start_as_current_span("my_operation"):
        ...
"""

import os
import re
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Cached tracer provider state
_telemetry_configured = False


def setup_telemetry(
    service_name: Optional[str] = None,
    service_version: Optional[str] = None,
) -> bool:
    """
    Configure OpenTelemetry tracing for the application.

    Reads configuration from environment variables:
    - OTEL_EXPORTER_OTLP_ENDPOINT: OTLP endpoint (e.g., http://localhost:4317)
    - APPLICATIONINSIGHTS_CONNECTION_STRING: Azure Monitor connection string
    - OTEL_TRACING_ENABLED: Enable/disable tracing (default: true if any exporter is configured)

    Args:
        service_name: Override service name (default: rfp-analyzer)
        service_version: Override service version (default: from pyproject.toml)

    Returns:
        True if tracing was successfully configured, False otherwise
    """
    global _telemetry_configured
    if _telemetry_configured:
        return True

    # Check if tracing is explicitly disabled
    tracing_env = os.getenv("OTEL_TRACING_ENABLED", "").lower()
    if tracing_env in ("false", "0", "no", "off"):
        logger.info("OpenTelemetry tracing explicitly disabled via OTEL_TRACING_ENABLED")
        _telemetry_configured = True
        return False

    svc_name = service_name or os.getenv("OTEL_SERVICE_NAME", "rfp-analyzer")
    svc_version = service_version or _get_app_version()

    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    ai_conn_str = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "")

    # If no exporters configured, skip setup
    if not otlp_endpoint and not ai_conn_str:
        logger.info(
            "No OTEL exporters configured (set OTEL_EXPORTER_OTLP_ENDPOINT or "
            "APPLICATIONINSIGHTS_CONNECTION_STRING to enable tracing)"
        )
        _telemetry_configured = True
        return False

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor
        from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION

        resource = Resource.create({
            SERVICE_NAME: svc_name,
            SERVICE_VERSION: svc_version,
            "deployment.environment": os.getenv("DEPLOYMENT_ENVIRONMENT", "development"),
        })

        provider = TracerProvider(resource=resource)
        exporters_added = 0

        # OTLP exporter (for Aspire Dashboard, Jaeger, etc.)
        if otlp_endpoint:
            try:
                from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

                otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
                provider.add_span_processor(SimpleSpanProcessor(otlp_exporter))
                exporters_added += 1
                logger.info("OTLP trace exporter configured: %s", otlp_endpoint)
            except ImportError:
                logger.warning(
                    "opentelemetry-exporter-otlp-proto-grpc not installed. "
                    "Install it to export traces to OTLP endpoints."
                )

        # Azure Monitor exporter (for Application Insights)
        if ai_conn_str:
            try:
                from azure.monitor.opentelemetry.exporter import AzureMonitorTraceExporter

                az_exporter = AzureMonitorTraceExporter(connection_string=ai_conn_str)
                provider.add_span_processor(SimpleSpanProcessor(az_exporter))
                exporters_added += 1
                logger.info("Azure Monitor trace exporter configured")
            except ImportError:
                logger.warning(
                    "azure-monitor-opentelemetry-exporter not installed. "
                    "Install it to export traces to Application Insights."
                )

        if exporters_added > 0:
            trace.set_tracer_provider(provider)
            _setup_agent_framework_observability()
            _telemetry_configured = True
            logger.info(
                "OpenTelemetry tracing initialized — service=%s, version=%s, exporters=%d",
                svc_name, svc_version, exporters_added,
            )
            return True
        else:
            logger.info("No OTEL trace exporters were successfully added")
            _telemetry_configured = True
            return False

    except ImportError:
        logger.warning("OpenTelemetry SDK not installed. Tracing disabled.")
        _telemetry_configured = True
        return False
    except Exception as e:
        logger.warning("Failed to setup OpenTelemetry tracing: %s", str(e))
        _telemetry_configured = True
        return False


def _setup_agent_framework_observability() -> None:
    """Enable Agent Framework's built-in observability if available."""
    try:
        from agent_framework.observability import configure_otel_providers

        enable_sensitive = os.getenv("ENABLE_SENSITIVE_DATA", "false").lower() in (
            "true", "1", "yes",
        )
        configure_otel_providers(enable_sensitive_data=enable_sensitive)
        logger.info("Agent Framework observability enabled (sensitive_data=%s)", enable_sensitive)
    except ImportError:
        logger.debug("agent_framework.observability not available — skipping")
    except Exception as e:
        logger.debug("Agent Framework observability setup failed: %s", e)


def get_tracer(name: str = __name__):
    """
    Get an OpenTelemetry tracer.

    Returns a no-op tracer if OTEL is not configured.

    Args:
        name: Tracer name (typically __name__)

    Returns:
        An OpenTelemetry Tracer instance
    """
    try:
        from opentelemetry import trace
        return trace.get_tracer(name, tracer_provider=trace.get_tracer_provider())
    except ImportError:
        return _NoOpTracer()


def _get_app_version() -> str:
    """Read version from pyproject.toml."""
    try:
        pyproject = Path(__file__).parent.parent / "pyproject.toml"
        if pyproject.exists():
            content = pyproject.read_text(encoding="utf-8")
            match = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)
            if match:
                return match.group(1)
    except Exception:
        pass
    return "0.0.0"


class _NoOpSpan:
    """Minimal no-op span when OTEL is not available."""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def set_attribute(self, key, value):
        pass

    def set_status(self, status):
        pass

    def record_exception(self, exception):
        pass

    def add_event(self, name, attributes=None):
        pass


class _NoOpTracer:
    """Minimal no-op tracer when OTEL is not available."""

    def start_as_current_span(self, name, **kwargs):
        return _NoOpSpan()

    def start_span(self, name, **kwargs):
        return _NoOpSpan()
