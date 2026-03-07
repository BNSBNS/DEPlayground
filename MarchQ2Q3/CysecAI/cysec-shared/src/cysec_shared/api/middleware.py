"""Shared API middleware: API key auth, rate limiting.

# SELF-SECURITY: RBAC — API key auth on all endpoints
# STRIDE: S=API key, D=rate limited
"""

from __future__ import annotations

from collections import defaultdict
from time import monotonic
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Validate API key from X-API-Key header.

    Exempts /health and /docs endpoints.
    """

    def __init__(self, app: Any, api_key: str) -> None:
        super().__init__(app)
        self._api_key = api_key

    async def dispatch(self, request: Any, call_next: Any) -> Any:
        path = request.url.path
        # Health and docs endpoints are public
        if path in ("/health", "/docs", "/openapi.json", "/redoc"):
            return await call_next(request)

        provided_key = request.headers.get("X-API-Key")
        if not provided_key or provided_key != self._api_key:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key", "error_code": "UNAUTHORIZED"},
            )
        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiter by client IP.

    Uses sliding window counter. Not suitable for multi-process deployments
    (use Redis-based limiter in production).
    """

    def __init__(self, app: Any, max_requests: int = 100, window_seconds: int = 60) -> None:
        super().__init__(app)
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Any, call_next: Any) -> Any:
        client_ip = request.client.host if request.client else "unknown"
        now = monotonic()
        cutoff = now - self._window_seconds

        # Prune old entries
        self._requests[client_ip] = [
            t for t in self._requests[client_ip] if t > cutoff
        ]

        if len(self._requests[client_ip]) >= self._max_requests:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded", "error_code": "RATE_LIMITED"},
            )

        self._requests[client_ip].append(now)
        return await call_next(request)
