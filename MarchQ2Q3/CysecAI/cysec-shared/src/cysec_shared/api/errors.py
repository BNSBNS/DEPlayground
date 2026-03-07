"""Standard error response model for all CysecAI APIs."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Consistent error format across all project APIs.

    Sanitizes internal details — no stack traces in responses.
    # SELF-SECURITY: Info Disclosure — errors sanitized
    """

    detail: str
    error_code: str = "INTERNAL_ERROR"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
