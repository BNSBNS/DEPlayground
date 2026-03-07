from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any

import asyncpg

from src.logging import get_logger
from src.models.sla import SLARecord
from src.models.versions import ContractVersion
from src.models.violations import Violation, ViolationSeverity, ViolationType

log = get_logger(__name__)


async def check_sla(
    pool: asyncpg.Pool, version: ContractVersion
) -> list[Violation]:
    """Check SLA compliance for the current period."""
    violations: list[Violation] = []
    sla_spec = version.sla_spec
    table = version.schema_spec.get("table", "")

    if not sla_spec or not table:
        return violations

    update_frequency_minutes = sla_spec.get("update_frequency_minutes", 60)
    max_latency_seconds = sla_spec.get("max_latency_seconds", 300)
    min_availability_pct = sla_spec.get("min_availability_pct", 99.0)
    window_hours = sla_spec.get("window_hours", 24)
    ts_column = sla_spec.get("timestamp_column", "updated_at")
    schema = version.schema_spec.get("schema", "public")

    now = datetime.utcnow()
    period_start = now - timedelta(hours=window_hours)

    # Count actual updates in the window
    actual_updates = await _count_updates(
        pool, schema, table, ts_column, period_start, now
    )
    expected_updates = int((window_hours * 60) / update_frequency_minutes)
    missed = max(0, expected_updates - actual_updates)

    # Compute max observed latency (gap between consecutive updates)
    max_observed_latency = await _max_gap_seconds(
        pool, schema, table, ts_column, period_start, now
    )

    # Availability = actual / expected (capped at 100)
    availability_pct = min(100.0, (actual_updates / max(expected_updates, 1)) * 100)

    compliant = (
        max_observed_latency <= max_latency_seconds
        and availability_pct >= min_availability_pct
    )

    # Store SLA record
    sla_record = SLARecord(
        contract_id=version.contract_id,
        period_start=period_start,
        period_end=now,
        expected_updates=expected_updates,
        actual_updates=actual_updates,
        missed_updates=missed,
        max_observed_latency=max_observed_latency,
        availability_pct=availability_pct,
        compliant=compliant,
    )
    await _store_sla_record(pool, sla_record)

    # Generate violations if non-compliant
    if max_observed_latency > max_latency_seconds:
        violations.append(
            Violation(
                contract_id=version.contract_id,
                version_id=version.id,
                violation_type=ViolationType.sla_breach,
                severity=ViolationSeverity.critical,
                dataset=table,
                expected=f"<= {max_latency_seconds}s latency",
                actual=f"{max_observed_latency:.0f}s",
                message=(
                    f"Max latency {max_observed_latency:.0f}s exceeds "
                    f"SLA threshold {max_latency_seconds}s"
                ),
            )
        )

    if availability_pct < min_availability_pct:
        violations.append(
            Violation(
                contract_id=version.contract_id,
                version_id=version.id,
                violation_type=ViolationType.sla_breach,
                severity=ViolationSeverity.critical,
                dataset=table,
                expected=f">= {min_availability_pct}%",
                actual=f"{availability_pct:.1f}%",
                message=(
                    f"Availability {availability_pct:.1f}% below "
                    f"SLA threshold {min_availability_pct}%"
                ),
            )
        )

    log.info(
        "sla_checked",
        table=table,
        compliant=compliant,
        availability=f"{availability_pct:.1f}%",
        max_latency=f"{max_observed_latency:.0f}s",
    )
    return violations


async def _count_updates(
    pool: asyncpg.Pool,
    schema: str,
    table: str,
    ts_column: str,
    start: datetime,
    end: datetime,
) -> int:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""
            SELECT COUNT(*) AS cnt
            FROM "{schema}"."{table}"
            WHERE "{ts_column}" BETWEEN $1 AND $2
            """,  # noqa: S608
            start,
            end,
        )
    return row["cnt"] if row else 0


async def _max_gap_seconds(
    pool: asyncpg.Pool,
    schema: str,
    table: str,
    ts_column: str,
    start: datetime,
    end: datetime,
) -> float:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT "{ts_column}" AS ts
            FROM "{schema}"."{table}"
            WHERE "{ts_column}" BETWEEN $1 AND $2
            ORDER BY "{ts_column}"
            LIMIT 10000
            """,  # noqa: S608
            start,
            end,
        )

    if len(rows) < 2:
        # If 0-1 rows, gap is the entire window
        return (end - start).total_seconds()

    max_gap = 0.0
    for i in range(1, len(rows)):
        gap = (rows[i]["ts"] - rows[i - 1]["ts"]).total_seconds()
        max_gap = max(max_gap, gap)

    return max_gap


async def _store_sla_record(pool: asyncpg.Pool, record: SLARecord) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO sla_records
                (id, contract_id, period_start, period_end,
                 expected_updates, actual_updates, missed_updates,
                 max_observed_latency, availability_pct, compliant)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            """,
            record.id,
            record.contract_id,
            record.period_start,
            record.period_end,
            record.expected_updates,
            record.actual_updates,
            record.missed_updates,
            record.max_observed_latency,
            record.availability_pct,
            record.compliant,
        )


async def get_sla_records(
    pool: asyncpg.Pool, contract_id: uuid.UUID
) -> list[SLARecord]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM sla_records
            WHERE contract_id = $1
            ORDER BY period_end DESC
            LIMIT 100
            """,
            contract_id,
        )
    return [
        SLARecord(
            id=r["id"],
            contract_id=r["contract_id"],
            period_start=r["period_start"],
            period_end=r["period_end"],
            expected_updates=r["expected_updates"],
            actual_updates=r["actual_updates"],
            missed_updates=r["missed_updates"],
            max_observed_latency=r["max_observed_latency"],
            availability_pct=r["availability_pct"],
            compliant=r["compliant"],
        )
        for r in rows
    ]
