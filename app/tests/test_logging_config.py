"""Tests for services.logging_config module."""

import logging
import pytest

from services.logging_config import get_logger, setup_logging


class TestGetLogger:
    """Tests for get_logger."""

    def test_returns_logger_instance(self):
        logger = get_logger("test.module")
        assert isinstance(logger, logging.Logger)

    def test_logger_name_matches(self):
        logger = get_logger("my.custom.name")
        assert logger.name == "my.custom.name"

    def test_returns_same_logger_for_same_name(self):
        a = get_logger("shared")
        b = get_logger("shared")
        assert a is b


class TestSetupLogging:
    """Tests for setup_logging."""

    def test_can_call_setup_multiple_times(self):
        """setup_logging should be idempotent (guarded by _logging_configured flag)."""
        # It has already been called by conftest indirectly; calling again should not raise.
        setup_logging()
        setup_logging()

    def test_root_logger_has_handlers_after_setup(self):
        setup_logging()
        root = logging.getLogger()
        # At least a console handler should exist
        assert len(root.handlers) > 0
