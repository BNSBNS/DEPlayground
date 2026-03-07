from __future__ import annotations

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    detail: str
    status_code: int = 500
