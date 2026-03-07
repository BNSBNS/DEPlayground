from __future__ import annotations

import asyncpg
import structlog

from src.config import get_settings

log = structlog.get_logger(__name__)

_pool: asyncpg.Pool | None = None

DDL = """
CREATE TABLE IF NOT EXISTS pipeline_events (
    id              UUID PRIMARY KEY,
    source          TEXT NOT NULL,
    severity        TEXT NOT NULL,
    pipeline_name   TEXT NOT NULL,
    task_name       TEXT NOT NULL,
    error_message   TEXT NOT NULL,
    error_type      TEXT NOT NULL DEFAULT 'unknown',
    affected_table  TEXT DEFAULT '',
    affected_column TEXT DEFAULT '',
    log_snippet     TEXT DEFAULT '',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS agent_runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id        UUID REFERENCES pipeline_events(id),
    status          TEXT NOT NULL DEFAULT 'pending',
    state_snapshot  JSONB DEFAULT '{}',
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS fix_proposals (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id          UUID REFERENCES agent_runs(id),
    fix_type        TEXT NOT NULL,
    file_path       TEXT DEFAULT '',
    content         TEXT NOT NULL,
    description     TEXT NOT NULL,
    risk_level      TEXT NOT NULL DEFAULT 'medium',
    pr_url          TEXT DEFAULT '',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS approval_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_id     UUID REFERENCES fix_proposals(id),
    action          TEXT NOT NULL,
    reviewer        TEXT DEFAULT '',
    comment         TEXT DEFAULT '',
    decided_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        settings = get_settings()
        _pool = await asyncpg.create_pool(
            dsn=settings.postgres_dsn,
            min_size=2,
            max_size=10,
        )
        await log.ainfo("db_pool_created")
    return _pool


async def init_db() -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(DDL)
    await log.ainfo("db_initialized")


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        await log.ainfo("db_pool_closed")
