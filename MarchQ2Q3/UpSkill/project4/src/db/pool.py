from __future__ import annotations

from typing import TYPE_CHECKING

import asyncpg

from src.config import settings
from src.logging import get_logger

if TYPE_CHECKING:
    pass

log = get_logger(__name__)

_pool: asyncpg.Pool | None = None

DDL_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS real_time_sales (
        id BIGSERIAL PRIMARY KEY,
        window_start TIMESTAMPTZ NOT NULL,
        window_end TIMESTAMPTZ NOT NULL,
        region TEXT NOT NULL,
        total_orders INTEGER NOT NULL DEFAULT 0,
        total_revenue NUMERIC(18,2) NOT NULL DEFAULT 0,
        avg_order_value NUMERIC(18,2) NOT NULL DEFAULT 0,
        cancelled_orders INTEGER NOT NULL DEFAULT 0,
        unique_customers INTEGER NOT NULL DEFAULT 0,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE (window_start, window_end, region)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS customer_activity (
        id BIGSERIAL PRIMARY KEY,
        customer_id TEXT NOT NULL,
        window_start TIMESTAMPTZ NOT NULL,
        window_end TIMESTAMPTZ NOT NULL,
        page_views INTEGER NOT NULL DEFAULT 0,
        product_views INTEGER NOT NULL DEFAULT 0,
        cart_additions INTEGER NOT NULL DEFAULT 0,
        searches INTEGER NOT NULL DEFAULT 0,
        orders_placed INTEGER NOT NULL DEFAULT 0,
        total_spent NUMERIC(18,2) NOT NULL DEFAULT 0,
        session_count INTEGER NOT NULL DEFAULT 0,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE (customer_id, window_start, window_end)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS product_performance (
        id BIGSERIAL PRIMARY KEY,
        product_id TEXT NOT NULL,
        window_start TIMESTAMPTZ NOT NULL,
        window_end TIMESTAMPTZ NOT NULL,
        views INTEGER NOT NULL DEFAULT 0,
        cart_additions INTEGER NOT NULL DEFAULT 0,
        orders INTEGER NOT NULL DEFAULT 0,
        revenue NUMERIC(18,2) NOT NULL DEFAULT 0,
        returns INTEGER NOT NULL DEFAULT 0,
        conversion_rate REAL NOT NULL DEFAULT 0,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE (product_id, window_start, window_end)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS anomaly_flags (
        id BIGSERIAL PRIMARY KEY,
        anomaly_id TEXT UNIQUE NOT NULL,
        rule_name TEXT NOT NULL,
        severity TEXT NOT NULL,
        entity_type TEXT NOT NULL,
        entity_id TEXT NOT NULL,
        metric_name TEXT NOT NULL,
        metric_value DOUBLE PRECISION NOT NULL,
        threshold DOUBLE PRECISION NOT NULL,
        description TEXT NOT NULL,
        detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        resolved BOOLEAN NOT NULL DEFAULT FALSE
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_rts_window ON real_time_sales (window_start, window_end)",
    "CREATE INDEX IF NOT EXISTS idx_rts_region ON real_time_sales (region)",
    "CREATE INDEX IF NOT EXISTS idx_ca_customer ON customer_activity (customer_id)",
    "CREATE INDEX IF NOT EXISTS idx_pp_product ON product_performance (product_id)",
    "CREATE INDEX IF NOT EXISTS idx_af_detected ON anomaly_flags (detected_at)",
    "CREATE INDEX IF NOT EXISTS idx_af_severity ON anomaly_flags (severity)",
]


async def get_pool() -> asyncpg.Pool:
    global _pool  # noqa: PLW0603
    if _pool is None:
        _pool = await asyncpg.create_pool(
            dsn=settings.postgres.dsn,
            min_size=2,
            max_size=10,
        )
        log.info("postgres_pool_created")
    return _pool


async def init_db() -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        for stmt in DDL_STATEMENTS:
            await conn.execute(stmt)
    log.info("database_initialized", tables=4)


async def close_pool() -> None:
    global _pool  # noqa: PLW0603
    if _pool is not None:
        await _pool.close()
        _pool = None
        log.info("postgres_pool_closed")
