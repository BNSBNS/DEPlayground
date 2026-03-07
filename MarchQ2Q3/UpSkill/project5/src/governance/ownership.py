from __future__ import annotations

import json
from typing import Any

import asyncpg

from src.logging import get_logger

log = get_logger(__name__)


async def get_dataset_owner(pool: asyncpg.Pool, dataset: str) -> dict[str, Any] | None:
    """Who owns this dataset?"""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, name, dataset, owner_team, owner_contact, status
            FROM contracts WHERE dataset = $1
            """,
            dataset,
        )
    if row is None:
        return None
    return dict(row)


async def get_team_datasets(pool: asyncpg.Pool, team: str) -> list[dict[str, Any]]:
    """What datasets does this team own?"""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, name, dataset, status, created_at
            FROM contracts WHERE owner_team = $1
            ORDER BY dataset
            """,
            team,
        )
    return [dict(r) for r in rows]


async def get_dataset_consumers(
    pool: asyncpg.Pool, dataset: str
) -> list[str]:
    """Who consumes this dataset?"""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT cv.consumers
            FROM contract_versions cv
            JOIN contracts c ON c.current_version_id = cv.id
            WHERE c.dataset = $1
            """,
            dataset,
        )
    if row is None:
        return []
    consumers = row["consumers"]
    if isinstance(consumers, str):
        return json.loads(consumers)
    return list(consumers)


async def get_ownership_summary(pool: asyncpg.Pool) -> dict[str, Any]:
    """Full ownership summary: teams, datasets, consumers."""
    async with pool.acquire() as conn:
        teams = await conn.fetch(
            """
            SELECT owner_team, COUNT(*) AS dataset_count
            FROM contracts
            GROUP BY owner_team
            ORDER BY dataset_count DESC
            """
        )
        total = await conn.fetchval("SELECT COUNT(*) FROM contracts")
        statuses = await conn.fetch(
            """
            SELECT status, COUNT(*) AS cnt
            FROM contracts
            GROUP BY status
            """
        )

    return {
        "total_contracts": total,
        "teams": [
            {"team": r["owner_team"], "dataset_count": r["dataset_count"]}
            for r in teams
        ],
        "status_breakdown": {r["status"]: r["cnt"] for r in statuses},
    }
