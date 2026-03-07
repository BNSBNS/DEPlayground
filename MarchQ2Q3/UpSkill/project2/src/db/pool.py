"""Asyncpg connection pool management with pgvector support."""

from __future__ import annotations

from typing import TYPE_CHECKING

import asyncpg

from src.logging import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger("db.pool")

_pool: asyncpg.Pool | None = None  # type: ignore[type-arg]

CREATE_TABLES_DDL = """
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

CREATE TABLE IF NOT EXISTS embeddings (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    entity_id   TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    content     TEXT NOT NULL,
    embedding   vector(384) NOT NULL,
    metadata    JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_embeddings_entity
    ON embeddings (entity_type, entity_id);

CREATE TABLE IF NOT EXISTS eval_results (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    question            TEXT NOT NULL,
    answer              TEXT NOT NULL,
    faithfulness        FLOAT,
    answer_relevancy    FLOAT,
    context_precision   FLOAT,
    context_recall      FLOAT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ingestion_runs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_type     TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'running',
    stats           JSONB DEFAULT '{}',
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at    TIMESTAMPTZ
);
"""


async def init_pool(dsn: str, min_size: int = 2, max_size: int = 10) -> asyncpg.Pool:  # type: ignore[type-arg]
    """Initialize the asyncpg connection pool and create tables."""
    global _pool  # noqa: PLW0603
    logger.info("initializing_pg_pool", dsn=dsn.split("@")[-1], min=min_size, max=max_size)
    _pool = await asyncpg.create_pool(dsn=dsn, min_size=min_size, max_size=max_size)
    async with _pool.acquire() as conn:
        await conn.execute(CREATE_TABLES_DDL)
    logger.info("pg_pool_ready")
    return _pool


async def close_pool() -> None:
    """Close the connection pool."""
    global _pool  # noqa: PLW0603
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("pg_pool_closed")


def get_pool() -> asyncpg.Pool:  # type: ignore[type-arg]
    """Get the active connection pool. Raises if not initialized."""
    if _pool is None:
        raise RuntimeError("Database pool not initialized. Call init_pool() first.")
    return _pool
