from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse


class FeatureStoreError(Exception):
    def __init__(self, message: str, status_code: int = 500) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class FeatureNotFoundError(FeatureStoreError):
    def __init__(self, name: str) -> None:
        super().__init__(f"Feature '{name}' not found", status_code=404)


class FeatureSetNotFoundError(FeatureStoreError):
    def __init__(self, name: str) -> None:
        super().__init__(f"Feature set '{name}' not found", status_code=404)


class ValidationError(FeatureStoreError):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__(f"Validation failed: {'; '.join(errors)}", status_code=422)


async def feature_store_error_handler(
    request: Request, exc: FeatureStoreError
) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.message},
    )
