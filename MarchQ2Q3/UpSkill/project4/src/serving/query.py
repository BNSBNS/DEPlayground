from __future__ import annotations

from datetime import datetime
from typing import Any

import asyncpg

from src.logging import get_logger

log = get_logger(__name__)


async def query_realtime_sales(
    pool: asyncpg.Pool,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    region: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Query real_time_sales with optional time-range and region filters."""
    conditions: list[str] = []
    params: list[Any] = []
    idx = 1

    if start:
        conditions.append(f"window_start >= ${idx}")
        params.append(start)
        idx += 1
    if end:
        conditions.append(f"window_end <= ${idx}")
        params.append(end)
        idx += 1
    if region:
        conditions.append(f"region = ${idx}")
        params.append(region)
        idx += 1

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params.append(limit)

    query = f"""
        SELECT * FROM real_time_sales
        {where}
        ORDER BY window_start DESC
        LIMIT ${idx}
    """

    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *params)
    return [dict(row) for row in rows]


async def query_product_performance(
    pool: asyncpg.Pool,
    *,
    product_id: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Query product_performance with optional filters."""
    conditions: list[str] = []
    params: list[Any] = []
    idx = 1

    if product_id:
        conditions.append(f"product_id = ${idx}")
        params.append(product_id)
        idx += 1
    if start:
        conditions.append(f"window_start >= ${idx}")
        params.append(start)
        idx += 1
    if end:
        conditions.append(f"window_end <= ${idx}")
        params.append(end)
        idx += 1

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params.append(limit)

    query = f"""
        SELECT * FROM product_performance
        {where}
        ORDER BY window_start DESC
        LIMIT ${idx}
    """

    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *params)
    return [dict(row) for row in rows]


async def query_customer_activity(
    pool: asyncpg.Pool,
    customer_id: str,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Query customer_activity for a specific customer."""
    conditions = ["customer_id = $1"]
    params: list[Any] = [customer_id]
    idx = 2

    if start:
        conditions.append(f"window_start >= ${idx}")
        params.append(start)
        idx += 1
    if end:
        conditions.append(f"window_end <= ${idx}")
        params.append(end)
        idx += 1

    where = f"WHERE {' AND '.join(conditions)}"
    params.append(limit)

    query = f"""
        SELECT * FROM customer_activity
        {where}
        ORDER BY window_start DESC
        LIMIT ${idx}
    """

    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *params)
    return [dict(row) for row in rows]


async def query_anomalies(
    pool: asyncpg.Pool,
    *,
    severity: str | None = None,
    resolved: bool | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Query anomaly_flags with optional filters."""
    conditions: list[str] = []
    params: list[Any] = []
    idx = 1

    if severity:
        conditions.append(f"severity = ${idx}")
        params.append(severity)
        idx += 1
    if resolved is not None:
        conditions.append(f"resolved = ${idx}")
        params.append(resolved)
        idx += 1

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params.append(limit)

    query = f"""
        SELECT * FROM anomaly_flags
        {where}
        ORDER BY detected_at DESC
        LIMIT ${idx}
    """

    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *params)
    return [dict(row) for row in rows]
