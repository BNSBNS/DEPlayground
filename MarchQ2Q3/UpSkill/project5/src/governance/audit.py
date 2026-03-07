from __future__ import annotations

import uuid
from typing import Any

import asyncpg

from src.config import settings
from src.logging import get_logger

log = get_logger(__name__)


async def record_audit(
    pool: asyncpg.Pool,
    entity_type: str,
    entity_id: uuid.UUID,
    action: str,
    actor: str,
    details: dict[str, Any] | None = None,
) -> None:
    """Append an entry to the audit log."""
    if not settings.governance.audit_enabled:
        return

    import json

    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO audit_log (entity_type, entity_id, action, actor, details)
            VALUES ($1, $2, $3, $4, $5)
            """,
            entity_type,
            entity_id,
            action,
            actor,
            json.dumps(details or {}),
        )

    log.info(
        "audit_recorded",
        entity_type=entity_type,
        entity_id=str(entity_id),
        action=action,
        actor=actor,
    )


async def get_audit_log(
    pool: asyncpg.Pool,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Query audit log with optional filters."""
    query = "SELECT * FROM audit_log WHERE 1=1"
    params: list[object] = []
    idx = 1

    if entity_type is not None:
        query += f" AND entity_type = ${idx}"
        params.append(entity_type)
        idx += 1

    if entity_id is not None:
        query += f" AND entity_id = ${idx}"
        params.append(entity_id)
        idx += 1

    query += f" ORDER BY created_at DESC LIMIT ${idx}"
    params.append(limit)

    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *params)

    return [dict(r) for r in rows]
