"""API middleware — auth, request ID, timing."""

from __future__ import annotations

import time
import uuid

from fastapi import HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from src.config import get_settings
from src.logging import get_logger

logger = get_logger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Add request ID and log request timing."""

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        request_id = str(uuid.uuid4())[:8]
        start = time.perf_counter()

        response = await call_next(request)

        elapsed = (time.perf_counter() - start) * 1000
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            elapsed_ms=f"{elapsed:.1f}",
            request_id=request_id,
        )
        return response


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Validate X-API-Key header (skip health endpoints)."""

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        if request.url.path.startswith("/health"):
            return await call_next(request)

        settings = get_settings()
        api_key = request.headers.get("X-API-Key")
        if api_key != settings.API_KEY:
            raise HTTPException(status_code=401, detail="Invalid API key")

        return await call_next(request)
