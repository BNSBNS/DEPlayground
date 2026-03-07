from __future__ import annotations

import asyncpg
import structlog

from src.config import Settings

logger = structlog.get_logger(__name__)

DDL_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS feature_definitions (
        name TEXT PRIMARY KEY,
        feature_set TEXT NOT NULL,
        entity TEXT NOT NULL,
        value_type TEXT NOT NULL,
        description TEXT DEFAULT '',
        owner TEXT DEFAULT '',
        tags TEXT[] DEFAULT '{}',
        batch_source TEXT,
        stream_source TEXT,
        aggregation JSONB,
        transform TEXT,
        freshness_sla_minutes INT DEFAULT 60,
        version INT DEFAULT 1,
        status TEXT DEFAULT 'active',
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS feature_sets (
        name TEXT PRIMARY KEY,
        entity TEXT NOT NULL,
        features TEXT[] DEFAULT '{}',
        batch_source TEXT,
        stream_source TEXT,
        schedule TEXT DEFAULT 'daily',
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS feature_values (
        entity_key TEXT NOT NULL,
        feature_name TEXT NOT NULL,
        value JSONB,
        event_timestamp TIMESTAMPTZ NOT NULL,
        created_timestamp TIMESTAMPTZ DEFAULT NOW()
    ) PARTITION BY RANGE (event_timestamp)
    """,
    """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_indexes
            WHERE indexname = 'idx_feature_values_lookup'
        ) THEN
            CREATE INDEX idx_feature_values_lookup
            ON feature_values (feature_name, entity_key, event_timestamp DESC);
        END IF;
    END $$
    """,
    """
    CREATE TABLE IF NOT EXISTS feature_stats (
        feature_name TEXT NOT NULL,
        window_start TIMESTAMPTZ NOT NULL,
        window_end TIMESTAMPTZ NOT NULL,
        count INT DEFAULT 0,
        null_count INT DEFAULT 0,
        null_pct DOUBLE PRECISION DEFAULT 0.0,
        mean DOUBLE PRECISION,
        stddev DOUBLE PRECISION,
        min_val DOUBLE PRECISION,
        max_val DOUBLE PRECISION,
        p25 DOUBLE PRECISION,
        p50 DOUBLE PRECISION,
        p75 DOUBLE PRECISION,
        p95 DOUBLE PRECISION,
        unique_count INT,
        value_distribution JSONB DEFAULT '{}',
        created_at TIMESTAMPTZ DEFAULT NOW(),
        PRIMARY KEY (feature_name, window_start, window_end)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS training_datasets (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        entity_type TEXT NOT NULL,
        features TEXT[] DEFAULT '{}',
        entity_df_ref TEXT DEFAULT '',
        created_at TIMESTAMPTZ DEFAULT NOW(),
        row_count INT DEFAULT 0
    )
    """,
]


async def create_pool(settings: Settings) -> asyncpg.Pool:
    pool: asyncpg.Pool = await asyncpg.create_pool(
        dsn=settings.postgres.dsn,
        min_size=2,
        max_size=10,
    )
    logger.info("database_pool_created", dsn=settings.postgres.dsn)
    return pool


async def run_migrations(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        for stmt in DDL_STATEMENTS:
            try:
                await conn.execute(stmt)
            except Exception:
                logger.exception("migration_failed", statement=stmt[:80])
                raise
    logger.info("migrations_complete", count=len(DDL_STATEMENTS))


async def close_pool(pool: asyncpg.Pool) -> None:
    await pool.close()
    logger.info("database_pool_closed")
