"""Structured logging configuration using structlog.

This module provides production-grade logging with:
- Structured JSON output for production environments
- Human-readable console output for development
- Correlation IDs for request tracing
- Consistent timestamp formatting
"""

import logging
import sys
from typing import Any

import structlog
from structlog.types import Processor

from src.common.config import Settings


def configure_logging(settings: Settings | None = None) -> None:
    """Configure structured logging for the application.

    Args:
        settings: Application settings. If None, will use default settings.
    """
    if settings is None:
        from src.common.config import get_settings

        settings = get_settings()

    # Determine log level
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Common processors for all environments
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if settings.log_json_format or settings.is_production():
        # Production: JSON format for log aggregation
        processors: list[Processor] = [
            *shared_processors,
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Development: Human-readable console output
        processors = [
            *shared_processors,
            structlog.dev.ConsoleRenderer(
                colors=True,
                exception_formatter=structlog.dev.plain_traceback,
            ),
        ]

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging to use structlog
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    # Reduce noise from third-party libraries
    logging.getLogger("kafka").setLevel(logging.WARNING)
    logging.getLogger("confluent_kafka").setLevel(logging.WARNING)


def get_logger(name: str | None = None, **initial_context: Any) -> structlog.BoundLogger:
    """Get a configured logger instance.

    Args:
        name: Logger name (typically __name__ of the calling module)
        **initial_context: Initial context values to bind to the logger

    Returns:
        A bound structlog logger instance
    """
    logger = structlog.get_logger(name)
    if initial_context:
        logger = logger.bind(**initial_context)
    return logger


def bind_context(**context: Any) -> None:
    """Bind context variables that will be included in all subsequent log messages.

    This is useful for adding request-scoped context like correlation IDs,
    user IDs, or other metadata that should appear in all related log entries.

    Args:
        **context: Key-value pairs to add to the logging context
    """
    structlog.contextvars.bind_contextvars(**context)


def clear_context() -> None:
    """Clear all bound context variables.

    Call this at the end of a request or processing cycle to avoid
    context leaking between unrelated operations.
    """
    structlog.contextvars.clear_contextvars()
