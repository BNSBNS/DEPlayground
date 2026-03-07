"""Simulate enforcement runs every 30-60s with realistic violation distribution.

Distribution: 75% pass, 15% quality failure, 7% SLA breach, 3% schema mismatch.
"""
from __future__ import annotations

import asyncio
import json
import random
import uuid
from datetime import datetime

import asyncpg

from src.config import settings
from src.logging import get_logger
from src.models.violations import ViolationSeverity, ViolationType

log = get_logger(__name__)

QUALITY_MESSAGES = [
    "Data staleness 4200s exceeds max 3600s",
    "Volume 5 below minimum 10 in 24h window",
    "Column 'name' null rate 12.3% exceeds max 5.0%",
    "Column 'id' has 3 duplicate values",
]

SLA_MESSAGES = [
    "Max latency 450s exceeds SLA threshold 300s",
    "Availability 97.2% below SLA threshold 99.0%",
    "Missed 8 of 24 expected updates",
]

SCHEMA_MESSAGES = [
    "Required column 'metadata' not found in table",
    "Column 'status' type mismatch: expected text, got integer",
    "Column 'name' should be NOT NULL",
]


async def simulate() -> None:
    log.info("starting_simulator")
    pool = await asyncpg.create_pool(dsn=settings.postgres.dsn, min_size=2, max_size=5)

    while True:
        delay = random.uniform(30, 60)

        # Pick a random contract
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT c.id AS contract_id, c.dataset, c.name, cv.id AS version_id
                FROM contracts c
                JOIN contract_versions cv ON cv.id = c.current_version_id
                ORDER BY random() LIMIT 1
                """
            )

        if row is None:
            log.warning("no_contracts_found")
            await asyncio.sleep(delay)
            continue

        contract_id = row["contract_id"]
        version_id = row["version_id"]
        dataset = row["dataset"]

        # Determine outcome: 75% pass, 15% quality, 7% sla, 3% schema
        roll = random.random()
        if roll < 0.75:
            # Pass - no violations
            log.info("enforcement_pass", dataset=dataset)
        elif roll < 0.90:
            # Quality failure
            await _insert_violation(
                pool,
                contract_id=contract_id,
                version_id=version_id,
                violation_type=ViolationType.quality_failure,
                severity=random.choice(
                    [ViolationSeverity.warning, ViolationSeverity.error]
                ),
                dataset=dataset,
                message=random.choice(QUALITY_MESSAGES),
            )
        elif roll < 0.97:
            # SLA breach
            await _insert_violation(
                pool,
                contract_id=contract_id,
                version_id=version_id,
                violation_type=ViolationType.sla_breach,
                severity=ViolationSeverity.critical,
                dataset=dataset,
                message=random.choice(SLA_MESSAGES),
            )
        else:
            # Schema mismatch
            await _insert_violation(
                pool,
                contract_id=contract_id,
                version_id=version_id,
                violation_type=ViolationType.schema_mismatch,
                severity=random.choice(
                    [ViolationSeverity.error, ViolationSeverity.critical]
                ),
                dataset=dataset,
                message=random.choice(SCHEMA_MESSAGES),
            )

        # Record audit
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO audit_log (entity_type, entity_id, action, actor, details)
                VALUES ($1, $2, $3, $4, $5)
                """,
                "enforcement",
                contract_id,
                "simulated_check",
                "simulator",
                json.dumps({"dataset": dataset, "roll": round(roll, 3)}),
            )

        log.info("simulation_tick", dataset=dataset, next_in=f"{delay:.0f}s")
        await asyncio.sleep(delay)


async def _insert_violation(
    pool: asyncpg.Pool,
    *,
    contract_id: uuid.UUID,
    version_id: uuid.UUID,
    violation_type: ViolationType,
    severity: ViolationSeverity,
    dataset: str,
    message: str,
) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO violations
                (id, contract_id, version_id, violation_type, severity,
                 dataset, message, detected_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
            uuid.uuid4(),
            contract_id,
            version_id,
            violation_type.value,
            severity.value,
            dataset,
            message,
            datetime.utcnow(),
        )
    log.info(
        "violation_simulated",
        type=violation_type.value,
        severity=severity.value,
        dataset=dataset,
    )


if __name__ == "__main__":
    asyncio.run(simulate())
