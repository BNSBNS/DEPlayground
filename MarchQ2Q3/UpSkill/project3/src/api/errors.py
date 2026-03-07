from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """Standard error response."""

    detail: str
    status_code: int = 500
