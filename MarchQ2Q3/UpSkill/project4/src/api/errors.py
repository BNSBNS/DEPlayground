from __future__ import annotations

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from src.logging import get_logger

log = get_logger(__name__)


class AppError(HTTPException):
    """Base application error."""

    def __init__(self, status_code: int = 500, detail: str = "Internal server error") -> None:
        super().__init__(status_code=status_code, detail=detail)


class NotFoundError(AppError):
    def __init__(self, resource: str, identifier: str) -> None:
        super().__init__(
            status_code=404, detail=f"{resource} '{identifier}' not found"
        )


class ServiceUnavailableError(AppError):
    def __init__(self, service: str) -> None:
        super().__init__(
            status_code=503, detail=f"Service '{service}' is unavailable"
        )


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled_error", path=request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )
