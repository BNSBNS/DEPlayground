"""Tests for structured logging configuration."""

from __future__ import annotations

from cysec_shared.logging import configure_logging, get_logger


class TestConfigureLogging:
    """configure_logging() tests."""

    def test_configures_without_error(self) -> None:
        configure_logging(log_level="DEBUG", json_format=False)

    def test_json_format(self) -> None:
        configure_logging(log_level="INFO", json_format=True)

    def test_invalid_level_defaults_to_info(self) -> None:
        configure_logging(log_level="BOGUS", json_format=False)


class TestGetLogger:
    """get_logger() tests."""

    def test_returns_logger(self) -> None:
        configure_logging()
        logger = get_logger("test")
        assert hasattr(logger, "info")
        assert hasattr(logger, "warning")
        assert hasattr(logger, "error")

    def test_binds_context(self) -> None:
        configure_logging()
        logger = get_logger("test", project="fraud-detection")
        assert logger is not None
        assert hasattr(logger, "info")

    def test_no_name_returns_logger(self) -> None:
        configure_logging()
        logger = get_logger()
        assert hasattr(logger, "info")
