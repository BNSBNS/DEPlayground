"""Asyncpg connection pool management."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import asyncpg

if TYPE_CHECKING:
    from src.config import PostgresSettings
from src.logging import get_logger

logger = get_logger(__name__)

_pool: asyncpg.Pool[asyncpg.Record] | None = None


async def init_pool(settings: PostgresSettings) -> asyncpg.Pool[asyncpg.Record]:
    """Create and return a connection pool."""
    global _pool  # noqa: PLW0603
    if _pool is not None:
        return _pool
    dsn = settings.get_dsn()
    _pool = await asyncpg.create_pool(
        dsn=dsn,
        min_size=settings.pool_min,
        max_size=settings.pool_max,
    )
    logger.info("Database pool initialized", host=settings.host, db=settings.db)
    return _pool


async def close_pool() -> None:
    """Close the connection pool."""
    global _pool  # noqa: PLW0603
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("Database pool closed")


def get_pool() -> asyncpg.Pool[asyncpg.Record]:
    """Get the current connection pool. Raises if not initialized."""
    if _pool is None:
        raise RuntimeError("Database pool not initialized. Call init_pool() first.")
    return _pool


async def create_tables(pool: asyncpg.Pool[asyncpg.Record]) -> None:
    """Create database tables if they don't exist."""
    ddl = """
    CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

    CREATE TABLE IF NOT EXISTS data_quality_metrics (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        table_name TEXT NOT NULL,
        database TEXT NOT NULL,
        schema_name TEXT NOT NULL DEFAULT 'public',
        metric_type TEXT NOT NULL,
        value DOUBLE PRECISION NOT NULL,
        expected_value DOUBLE PRECISION,
        threshold_warning DOUBLE PRECISION,
        threshold_critical DOUBLE PRECISION,
        status TEXT NOT NULL DEFAULT 'unknown',
        metadata JSONB NOT NULL DEFAULT '{}',
        measured_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_metrics_table_type
        ON data_quality_metrics (table_name, database, metric_type);
    CREATE INDEX IF NOT EXISTS idx_metrics_measured_at
        ON data_quality_metrics (measured_at DESC);

    CREATE TABLE IF NOT EXISTS schema_snapshots (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        table_name TEXT NOT NULL,
        database TEXT NOT NULL,
        schema_name TEXT NOT NULL DEFAULT 'public',
        columns JSONB NOT NULL,
        captured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE (table_name, database, schema_name)
    );

    CREATE TABLE IF NOT EXISTS alerts (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        severity TEXT NOT NULL,
        state TEXT NOT NULL DEFAULT 'open',
        source_table TEXT NOT NULL,
        source_metric_type TEXT NOT NULL,
        root_cause TEXT,
        suggested_remediation TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        acknowledged_at TIMESTAMPTZ,
        resolved_at TIMESTAMPTZ
    );
    CREATE INDEX IF NOT EXISTS idx_alerts_state ON alerts (state);
    CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alerts (severity);

    CREATE TABLE IF NOT EXISTS lineage_edges (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        source_id TEXT NOT NULL,
        target_id TEXT NOT NULL,
        relationship TEXT NOT NULL,
        transformation TEXT,
        UNIQUE (source_id, target_id, relationship)
    );

    CREATE TABLE IF NOT EXISTS remediation_log (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        alert_id UUID NOT NULL REFERENCES alerts(id),
        action_type TEXT NOT NULL,
        action_detail JSONB NOT NULL DEFAULT '{}',
        executed_by TEXT NOT NULL DEFAULT 'system',
        result TEXT NOT NULL DEFAULT 'skipped',
        executed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    """
    async with pool.acquire() as conn:
        await conn.execute(ddl)
    logger.info("Database tables created/verified")


async def save_metric(
    pool: asyncpg.Pool[asyncpg.Record], metric: Any
) -> None:
    """Persist a DataQualityMetric to the database."""
    await pool.execute(
        """
        INSERT INTO data_quality_metrics
            (id, table_name, database, schema_name, metric_type, value,
             expected_value, threshold_warning, threshold_critical, status,
             metadata, measured_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
        """,
        metric.id,
        metric.table_name,
        metric.database,
        metric.schema_name,
        metric.metric_type.value,
        metric.value,
        metric.expected_value,
        metric.threshold_warning,
        metric.threshold_critical,
        metric.status.value,
        metric.metadata,
        metric.measured_at,
    )
