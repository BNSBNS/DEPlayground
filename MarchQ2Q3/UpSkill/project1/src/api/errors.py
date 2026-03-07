"""Shared error response model."""

from datetime import datetime

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Standard error response for all API errors."""

    detail: str
    error_code: str = "INTERNAL_ERROR"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
