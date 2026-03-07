from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query

from src.api.dependencies import get_db_pool

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("/{customer_id}/activity")
async def get_customer_activity(
    customer_id: str,
    start: datetime | None = Query(None, description="Window start (ISO 8601)"),
    end: datetime | None = Query(None, description="Window end (ISO 8601)"),
    limit: int = Query(50, ge=1, le=500),
    pool: Any = Depends(get_db_pool),
) -> list[dict[str, Any]]:
    """Get activity timeline for a specific customer."""
    from src.serving.query import query_customer_activity

    return await query_customer_activity(
        pool, customer_id, start=start, end=end, limit=limit
    )
