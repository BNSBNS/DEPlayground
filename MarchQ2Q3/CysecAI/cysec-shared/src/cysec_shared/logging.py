"""Structured logging configuration using structlog.

Pattern mirrors UpSkill/project1/src/logging.py.
Usage:
    from cysec_shared.logging import configure_logging, get_logger

    configure_logging(log_level="INFO", json_format=False)
    logger = get_logger(__name__)
    logger.info("starting", port=8101)
"""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from structlog.types import Processor


def configure_logging(log_level: str = "INFO", json_format: bool = False) -> None:
    """Configure structured logging for the application."""
    level = getattr(logging, log_level.upper(), logging.INFO)

    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if json_format:
        processors: list[Processor] = [
            *shared_processors,
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
    else:
        processors = [
            *shared_processors,
            structlog.dev.ConsoleRenderer(
                colors=True,
                exception_formatter=structlog.dev.plain_traceback,
            ),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)


def get_logger(name: str | None = None, **context: Any) -> Any:
    """Get a configured logger instance with optional bound context."""
    logger = structlog.get_logger(name)
    if context:
        logger = logger.bind(**context)
    return logger
