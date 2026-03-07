from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query

from src.api.dependencies import get_db_pool

router = APIRouter(prefix="/sales", tags=["sales"])


@router.get("/realtime")
async def get_realtime_sales(
    start: datetime | None = Query(None, description="Window start (ISO 8601)"),
    end: datetime | None = Query(None, description="Window end (ISO 8601)"),
    region: str | None = Query(None, description="Filter by region"),
    limit: int = Query(100, ge=1, le=1000),
    pool: Any = Depends(get_db_pool),
) -> list[dict[str, Any]]:
    """Get real-time sales aggregations with optional time/region filters."""
    from src.serving.query import query_realtime_sales

    return await query_realtime_sales(
        pool, start=start, end=end, region=region, limit=limit
    )
