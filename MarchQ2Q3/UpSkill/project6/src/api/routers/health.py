from __future__ import annotations

from typing import Any

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, Any]:
    return {"status": "ok", "service": "ml-feature-store"}


@router.get("/ready")
async def ready() -> dict[str, Any]:
    return {"status": "ready"}
