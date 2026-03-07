from __future__ import annotations

import asyncpg

from src.config import settings
from src.logging import get_logger

log = get_logger(__name__)

_pool: asyncpg.Pool | None = None

DDL = """
CREATE TABLE IF NOT EXISTS contracts (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    dataset TEXT NOT NULL UNIQUE,
    owner_team TEXT NOT NULL,
    owner_contact TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    current_version_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS contract_versions (
    id UUID PRIMARY KEY,
    contract_id UUID NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
    version TEXT NOT NULL,
    schema_spec JSONB NOT NULL DEFAULT '{}',
    quality_spec JSONB NOT NULL DEFAULT '{}',
    sla_spec JSONB NOT NULL DEFAULT '{}',
    consumers JSONB NOT NULL DEFAULT '[]',
    changelog TEXT NOT NULL DEFAULT '',
    published_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(contract_id, version)
);

CREATE TABLE IF NOT EXISTS violations (
    id UUID PRIMARY KEY,
    contract_id UUID NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
    version_id UUID NOT NULL REFERENCES contract_versions(id) ON DELETE CASCADE,
    violation_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    dataset TEXT NOT NULL,
    field_name TEXT,
    expected TEXT,
    actual TEXT,
    message TEXT NOT NULL,
    detected_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_violations_dataset ON violations(dataset);
CREATE INDEX IF NOT EXISTS idx_violations_contract ON violations(contract_id);
CREATE INDEX IF NOT EXISTS idx_violations_detected ON violations(detected_at);

CREATE TABLE IF NOT EXISTS sla_records (
    id UUID PRIMARY KEY,
    contract_id UUID NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
    period_start TIMESTAMPTZ NOT NULL,
    period_end TIMESTAMPTZ NOT NULL,
    expected_updates INT NOT NULL,
    actual_updates INT NOT NULL,
    missed_updates INT NOT NULL,
    max_observed_latency DOUBLE PRECISION NOT NULL,
    availability_pct DOUBLE PRECISION NOT NULL,
    compliant BOOLEAN NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sla_contract ON sla_records(contract_id);

CREATE TABLE IF NOT EXISTS audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type TEXT NOT NULL,
    entity_id UUID NOT NULL,
    action TEXT NOT NULL,
    actor TEXT NOT NULL,
    details JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_log(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log(created_at);
"""


async def init_pool() -> asyncpg.Pool:
    global _pool
    if _pool is not None:
        return _pool

    log.info("creating_db_pool", dsn=settings.postgres.dsn[:30] + "...")
    _pool = await asyncpg.create_pool(
        dsn=settings.postgres.dsn,
        min_size=2,
        max_size=10,
    )
    async with _pool.acquire() as conn:
        await conn.execute(DDL)
    log.info("db_pool_ready")
    return _pool


async def get_pool() -> asyncpg.Pool:
    if _pool is None:
        return await init_pool()
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        log.info("db_pool_closed")
