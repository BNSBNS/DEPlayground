"""Seed the database with 15 contracts across 5 teams, 3 versions each."""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timedelta

import asyncpg

from src.config import settings
from src.logging import get_logger

log = get_logger(__name__)

TEAMS = [
    ("platform-engineering", "platform-eng@company.com"),
    ("data-engineering", "data-eng@company.com"),
    ("fintech-team", "fintech@company.com"),
    ("analytics-team", "analytics@company.com"),
    ("ml-team", "ml-team@company.com"),
]

DATASETS = [
    "orders",
    "customers",
    "payments",
    "products",
    "inventory",
    "shipments",
    "returns",
    "reviews",
    "sessions",
    "page_views",
    "cart_events",
    "user_preferences",
    "notifications",
    "audit_trails",
    "feature_flags",
]

COLUMN_TEMPLATES: dict[str, dict[str, dict[str, object]]] = {
    "default": {
        "id": {"type": "uuid", "nullable": False},
        "created_at": {"type": "timestamptz", "nullable": False},
        "updated_at": {"type": "timestamptz", "nullable": False},
    },
}

CONSUMERS = [
    "analytics-team",
    "billing-service",
    "reporting-dashboard",
    "ml-pipeline",
    "marketing-team",
    "support-team",
    "fraud-detection",
]


def _build_schema(dataset: str, version_num: int) -> dict[str, object]:
    columns: dict[str, dict[str, object]] = {
        "id": {"type": "uuid", "nullable": False},
        "created_at": {"type": "timestamptz", "nullable": False},
        "updated_at": {"type": "timestamptz", "nullable": False},
        "name": {"type": "text", "nullable": False},
        "status": {"type": "text", "nullable": False},
    }
    if version_num >= 2:
        columns["category"] = {"type": "text", "nullable": True}
    if version_num >= 3:
        columns["metadata"] = {"type": "jsonb", "nullable": True}
    return {"schema": "public", "table": dataset, "columns": columns}


def _build_quality(version_num: int) -> dict[str, object]:
    max_null = 5.0 - version_num  # Gets stricter each version
    return {
        "rules": {
            "freshness": {"timestamp_column": "updated_at", "max_staleness_seconds": 3600},
            "volume": {
                "min_rows": 10 * version_num,
                "window_hours": 24,
                "timestamp_column": "created_at",
            },
            "completeness": {"max_null_pct": max_null, "columns": ["id", "name"]},
            "uniqueness": {"columns": ["id"]},
        }
    }


def _build_sla(version_num: int) -> dict[str, object]:
    return {
        "update_frequency_minutes": max(5, 60 // version_num),
        "max_latency_seconds": max(30, 300 // version_num),
        "min_availability_pct": 99.0 + (version_num * 0.3),
        "window_hours": 24,
        "timestamp_column": "updated_at",
    }


async def seed() -> None:
    log.info("seeding_database")
    pool = await asyncpg.create_pool(dsn=settings.postgres.dsn, min_size=2, max_size=5)

    # Run DDL first
    from src.db.pool import DDL

    async with pool.acquire() as conn:
        await conn.execute(DDL)

    for i, dataset in enumerate(DATASETS):
        team_name, team_contact = TEAMS[i % len(TEAMS)]
        contract_id = uuid.uuid4()
        now = datetime.utcnow()

        # Create contract
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO contracts
                    (id, name, dataset, owner_team, owner_contact, status, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (dataset) DO NOTHING
                """,
                contract_id,
                f"{dataset.replace('_', ' ').title()} Contract",
                dataset,
                team_name,
                team_contact,
                "active",
                now - timedelta(days=90),
                now,
            )

        # Create 3 versions
        last_version_id = None
        for v in range(1, 4):
            version_id = uuid.uuid4()
            last_version_id = version_id
            consumers = CONSUMERS[: (v + 1)]

            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO contract_versions
                        (id, contract_id, version, schema_spec, quality_spec,
                         sla_spec, consumers, changelog, published_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    ON CONFLICT (contract_id, version) DO NOTHING
                    """,
                    version_id,
                    contract_id,
                    f"{v}.0.0",
                    json.dumps(_build_schema(dataset, v)),
                    json.dumps(_build_quality(v)),
                    json.dumps(_build_sla(v)),
                    json.dumps(consumers),
                    f"Version {v}.0.0 - {'initial' if v == 1 else 'updated'} contract",
                    now - timedelta(days=90 - (v * 30)),
                )

        # Set current version
        if last_version_id:
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE contracts SET current_version_id = $1 WHERE id = $2",
                    last_version_id,
                    contract_id,
                )

        log.info("seeded_contract", dataset=dataset, team=team_name)

    await pool.close()
    log.info("seeding_complete", total_contracts=len(DATASETS))


if __name__ == "__main__":
    asyncio.run(seed())
