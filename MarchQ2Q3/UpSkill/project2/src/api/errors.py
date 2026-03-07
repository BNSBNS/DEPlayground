"""Shared error response model for API error handling."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    detail: str
    error_code: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
