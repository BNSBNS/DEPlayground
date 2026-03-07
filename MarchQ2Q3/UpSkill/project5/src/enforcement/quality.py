from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import asyncpg

from src.logging import get_logger
from src.models.versions import ContractVersion
from src.models.violations import Violation, ViolationSeverity, ViolationType

log = get_logger(__name__)


async def check_quality(
    pool: asyncpg.Pool, version: ContractVersion
) -> list[Violation]:
    """Run quality checks defined in the contract's quality_spec."""
    violations: list[Violation] = []
    quality_spec = version.quality_spec
    table = version.schema_spec.get("table", "")
    schema = version.schema_spec.get("schema", "public")

    if not table or not quality_spec:
        return violations

    rules: dict[str, Any] = quality_spec.get("rules", {})

    # Freshness check
    freshness = rules.get("freshness")
    if freshness:
        v = await _check_freshness(pool, version, schema, table, freshness)
        if v:
            violations.append(v)

    # Volume check
    volume = rules.get("volume")
    if volume:
        v = await _check_volume(pool, version, schema, table, volume)
        if v:
            violations.append(v)

    # Completeness (null %) per column
    completeness = rules.get("completeness")
    if completeness:
        vs = await _check_completeness(pool, version, schema, table, completeness)
        violations.extend(vs)

    # Uniqueness per column
    uniqueness = rules.get("uniqueness")
    if uniqueness:
        vs = await _check_uniqueness(pool, version, schema, table, uniqueness)
        violations.extend(vs)

    log.info("quality_checked", table=table, violation_count=len(violations))
    return violations


async def _check_freshness(
    pool: asyncpg.Pool,
    version: ContractVersion,
    schema: str,
    table: str,
    spec: dict[str, Any],
) -> Violation | None:
    ts_column = spec.get("timestamp_column", "updated_at")
    max_staleness_seconds = spec.get("max_staleness_seconds", 3600)

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f'SELECT MAX("{ts_column}") AS latest FROM "{schema}"."{table}"'  # noqa: S608
        )

    if row is None or row["latest"] is None:
        return Violation(
            contract_id=version.contract_id,
            version_id=version.id,
            violation_type=ViolationType.quality_failure,
            severity=ViolationSeverity.error,
            dataset=table,
            field_name=ts_column,
            expected=f"data within {max_staleness_seconds}s",
            actual="no data found",
            message=f"Table {table} has no data for freshness check",
        )

    age = (datetime.utcnow() - row["latest"].replace(tzinfo=None)).total_seconds()
    if age > max_staleness_seconds:
        return Violation(
            contract_id=version.contract_id,
            version_id=version.id,
            violation_type=ViolationType.quality_failure,
            severity=ViolationSeverity.error,
            dataset=table,
            field_name=ts_column,
            expected=f"<= {max_staleness_seconds}s",
            actual=f"{age:.0f}s",
            message=(
                f"Data staleness {age:.0f}s exceeds "
                f"max {max_staleness_seconds}s"
            ),
        )
    return None


async def _check_volume(
    pool: asyncpg.Pool,
    version: ContractVersion,
    schema: str,
    table: str,
    spec: dict[str, Any],
) -> Violation | None:
    min_rows = spec.get("min_rows", 0)
    max_rows = spec.get("max_rows")
    window_hours = spec.get("window_hours", 24)
    ts_column = spec.get("timestamp_column", "created_at")

    cutoff = datetime.utcnow() - timedelta(hours=window_hours)

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""
            SELECT COUNT(*) AS cnt
            FROM "{schema}"."{table}"
            WHERE "{ts_column}" >= $1
            """,  # noqa: S608
            cutoff,
        )

    count = row["cnt"] if row else 0

    if count < min_rows:
        return Violation(
            contract_id=version.contract_id,
            version_id=version.id,
            violation_type=ViolationType.quality_failure,
            severity=ViolationSeverity.error,
            dataset=table,
            expected=f">= {min_rows} rows in {window_hours}h",
            actual=f"{count} rows",
            message=f"Volume {count} below minimum {min_rows} in {window_hours}h window",
        )

    if max_rows is not None and count > max_rows:
        return Violation(
            contract_id=version.contract_id,
            version_id=version.id,
            violation_type=ViolationType.quality_failure,
            severity=ViolationSeverity.warning,
            dataset=table,
            expected=f"<= {max_rows} rows in {window_hours}h",
            actual=f"{count} rows",
            message=f"Volume {count} exceeds maximum {max_rows} in {window_hours}h window",
        )

    return None


async def _check_completeness(
    pool: asyncpg.Pool,
    version: ContractVersion,
    schema: str,
    table: str,
    spec: dict[str, Any],
) -> list[Violation]:
    violations: list[Violation] = []
    max_null_pct = spec.get("max_null_pct", 5.0)
    columns: list[str] = spec.get("columns", [])

    for col in columns:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                f"""
                SELECT
                    COUNT(*) AS total,
                    COUNT(*) FILTER (WHERE "{col}" IS NULL) AS nulls
                FROM "{schema}"."{table}"
                """,  # noqa: S608
            )

        if row and row["total"] > 0:
            null_pct = (row["nulls"] / row["total"]) * 100
            if null_pct > max_null_pct:
                violations.append(
                    Violation(
                        contract_id=version.contract_id,
                        version_id=version.id,
                        violation_type=ViolationType.quality_failure,
                        severity=ViolationSeverity.error,
                        dataset=table,
                        field_name=col,
                        expected=f"<= {max_null_pct}% nulls",
                        actual=f"{null_pct:.1f}% nulls",
                        message=(
                            f"Column '{col}' null rate {null_pct:.1f}% "
                            f"exceeds max {max_null_pct}%"
                        ),
                    )
                )

    return violations


async def _check_uniqueness(
    pool: asyncpg.Pool,
    version: ContractVersion,
    schema: str,
    table: str,
    spec: dict[str, Any],
) -> list[Violation]:
    violations: list[Violation] = []
    columns: list[str] = spec.get("columns", [])

    for col in columns:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                f"""
                SELECT
                    COUNT(*) AS total,
                    COUNT(DISTINCT "{col}") AS distinct_count
                FROM "{schema}"."{table}"
                """,  # noqa: S608
            )

        if row and row["total"] > 0 and row["distinct_count"] < row["total"]:
            dup_count = row["total"] - row["distinct_count"]
            violations.append(
                Violation(
                    contract_id=version.contract_id,
                    version_id=version.id,
                    violation_type=ViolationType.quality_failure,
                    severity=ViolationSeverity.error,
                    dataset=table,
                    field_name=col,
                    expected="all unique",
                    actual=f"{dup_count} duplicates",
                    message=f"Column '{col}' has {dup_count} duplicate values",
                )
            )

    return violations
