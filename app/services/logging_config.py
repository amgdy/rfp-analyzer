"""
Centralized Logging Configuration for RFP Analyzer.

This module provides unified logging configuration with:
- Console handler (stdout)
- File handler (rotating log files)
- OpenTelemetry handler (Azure Monitor / Log Analytics)
- OTLP log exporter (Aspire Dashboard, Jaeger, etc.)

Usage:
    from services.logging_config import setup_logging, get_logger
    
    # Call once at application startup (in main.py)
    setup_logging()
    
    # Get logger in any module
    logger = get_logger(__name__)
"""

import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

# Default configuration
DEFAULT_LOG_FORMAT = '%(asctime)s.%(msecs)03d | %(levelname)s | %(name)s | %(message)s'
DEFAULT_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
DEFAULT_LOG_LEVEL = logging.INFO
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_FILE = "rfp_analyzer.log"
MAX_LOG_SIZE = 10 * 1024 * 1024  # 10 MB
BACKUP_COUNT = 5

# Track if logging has been configured
_logging_configured = False


def _get_otel_enabled_default() -> bool:
    """Get default value for log_to_otel from environment variable.
    
    Defaults to True when APPLICATIONINSIGHTS_CONNECTION_STRING is set,
    allowing explicit override via OTEL_LOGGING_ENABLED=false.
    """
    env_value = os.getenv("OTEL_LOGGING_ENABLED", "").lower()
    if env_value:
        return env_value in ("true", "1", "yes", "on")
    # Auto-enable when App Insights connection string is available
    return bool(os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING"))


def setup_logging(
    level: int = DEFAULT_LOG_LEVEL,
    log_to_console: bool = True,
    log_to_file: bool = True,
    log_to_otel: Optional[bool] = None,  # Defaults to OTEL_LOGGING_ENABLED env var
    log_dir: Optional[Path] = None,
    connection_string: Optional[str] = None,
) -> None:
    """
    Configure unified logging for the application.
    
    Args:
        level: Logging level (default: INFO)
        log_to_console: Enable console logging (default: True)
        log_to_file: Enable file logging (default: True)
        log_to_otel: Enable OpenTelemetry/Azure Monitor logging 
                     (default: from OTEL_LOGGING_ENABLED env var, or True if not set)
        log_dir: Directory for log files (default: app/logs)
        connection_string: App Insights connection string (default: from env)
    """
    global _logging_configured
    
    if _logging_configured:
        return
    
    # Resolve log_to_otel default from environment if not explicitly provided
    if log_to_otel is None:
        log_to_otel = _get_otel_enabled_default()
    
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Create formatter
    formatter = logging.Formatter(DEFAULT_LOG_FORMAT, DEFAULT_DATE_FORMAT)
    
    # Console Handler
    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
    
    # File Handler
    if log_to_file:
        log_path = log_dir or LOG_DIR
        log_path.mkdir(parents=True, exist_ok=True)
        
        file_handler = RotatingFileHandler(
            log_path / LOG_FILE,
            maxBytes=MAX_LOG_SIZE,
            backupCount=BACKUP_COUNT,
            encoding='utf-8'
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    # OpenTelemetry Handler (Azure Monitor)
    # Only initialize if explicitly enabled - no SDK loaded otherwise
    otel_enabled = False
    if log_to_otel:
        conn_str = connection_string or os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
        if conn_str:
            otel_enabled = _setup_otel_logging(root_logger, conn_str, level)

    # OTLP Log Exporter (for Aspire Dashboard, Jaeger, etc.)
    otlp_log_enabled = False
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    if otlp_endpoint:
        otlp_log_enabled = _setup_otlp_logging(root_logger, otlp_endpoint, level)
    
    # Suppress noisy loggers from being sent to all handlers
    # These generate high volume logs that can cause throttling (HTTP 439)
    _suppress_noisy_loggers()
    
    _logging_configured = True
    
    # Log startup message
    startup_logger = logging.getLogger("rfp_analyzer.logging")
    startup_logger.info(
        "Logging initialized - Console: %s, File: %s, Azure Monitor: %s, OTLP: %s",
        log_to_console, log_to_file, otel_enabled, otlp_log_enabled,
    )


def _setup_otel_logging(root_logger: logging.Logger, connection_string: str, level: int) -> bool:
    """
    Set up OpenTelemetry logging handler for Azure Monitor.
    
    Args:
        root_logger: The root logger to attach the handler to
        connection_string: Azure Monitor connection string
        level: Logging level
    
    Returns:
        True if OTEL logging was successfully set up, False otherwise
    """
    try:
        # Lazy import - only load OTEL SDK when actually needed
        from opentelemetry._logs import set_logger_provider
        from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
        from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
        from azure.monitor.opentelemetry.exporter import AzureMonitorLogExporter
        
        # Create logger provider
        logger_provider = LoggerProvider()
        set_logger_provider(logger_provider)
        
        # Create Azure Monitor exporter with optimized settings
        exporter = AzureMonitorLogExporter(
            connection_string=connection_string,
            # Reduce timeout to avoid long waits (default is 10s)
            connection_timeout=5,
        )
        
        # Add batch processor with optimized settings for better performance
        # - Larger batch = fewer HTTP requests
        # - Longer interval = less frequent exports
        # - Shorter timeout = don't block shutdown too long
        logger_provider.add_log_record_processor(
            BatchLogRecordProcessor(
                exporter,
                max_queue_size=2048,           # Buffer more logs before dropping (default: 2048)
                schedule_delay_millis=5000,    # Export every 5 seconds (default: 5000)
                max_export_batch_size=512,     # Larger batches = fewer HTTP calls (default: 512)
                export_timeout_millis=10000,   # 10s timeout for export (default: 30000)
            )
        )
        
        # Create and add OpenTelemetry handler
        otel_handler = LoggingHandler(
            level=level,
            logger_provider=logger_provider
        )
        root_logger.addHandler(otel_handler)
        return True
        
    except ImportError:
        # OTEL packages not installed
        logging.getLogger("rfp_analyzer.logging").warning(
            "OpenTelemetry packages not installed. OTEL logging disabled."
        )
        return False
    except Exception as e:
        # Don't fail startup if OTEL setup fails
        logging.getLogger("rfp_analyzer.logging").warning(
            "Failed to setup OpenTelemetry logging: %s", str(e)
        )
        return False


def _setup_otlp_logging(root_logger: logging.Logger, endpoint: str, level: int) -> bool:
    """
    Set up OTLP log exporter for Aspire Dashboard / generic OTLP collector.

    Args:
        root_logger: The root logger to attach the handler to
        endpoint: OTLP endpoint URL (e.g., http://localhost:4317)
        level: Logging level

    Returns:
        True if OTLP logging was successfully set up, False otherwise
    """
    try:
        from opentelemetry._logs import set_logger_provider
        from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
        from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
        from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
        from opentelemetry.sdk.resources import Resource, SERVICE_NAME

        resource = Resource.create({
            SERVICE_NAME: "rfp-analyzer",
        })

        logger_provider = LoggerProvider(resource=resource)

        otlp_exporter = OTLPLogExporter(endpoint=endpoint, insecure=True)
        logger_provider.add_log_record_processor(
            BatchLogRecordProcessor(
                otlp_exporter,
                max_queue_size=2048,
                schedule_delay_millis=3000,
                max_export_batch_size=512,
                export_timeout_millis=10000,
            )
        )

        set_logger_provider(logger_provider)

        otel_handler = LoggingHandler(
            level=level,
            logger_provider=logger_provider,
        )
        root_logger.addHandler(otel_handler)
        return True

    except ImportError:
        logging.getLogger("rfp_analyzer.logging").debug(
            "OTLP log exporter packages not installed — OTLP logging disabled."
        )
        return False
    except Exception as e:
        logging.getLogger("rfp_analyzer.logging").warning(
            "Failed to setup OTLP logging: %s", str(e)
        )
        return False


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the specified name.
    
    This is the preferred way to get a logger in all modules.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


def set_log_level(level: int, logger_name: Optional[str] = None) -> None:
    """
    Dynamically change log level.
    
    Args:
        level: New logging level
        logger_name: Specific logger name, or None for root logger
    """
    logger = logging.getLogger(logger_name)
    logger.setLevel(level)
    for handler in logger.handlers:
        handler.setLevel(level)


def _suppress_noisy_loggers() -> None:
    """
    Suppress verbose loggers that generate high volume telemetry.
    
    These loggers can cause App Insights throttling (HTTP 439) due to
    excessive telemetry volume. Set them to WARNING or higher.
    """
    noisy_loggers = [
        # Azure SDK HTTP logging - very verbose, logs every HTTP request/response
        "azure.core.pipeline.policies.http_logging_policy",
        # HTTP libraries - can be very chatty
        "urllib3.connectionpool",
        "httpx",
        "httpcore",
    ]
    
    for logger_name in noisy_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)
