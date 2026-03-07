from __future__ import annotations

from typing import Any

import asyncpg

from src.logging import get_logger
from src.models.versions import ContractVersion
from src.models.violations import Violation, ViolationSeverity, ViolationType

log = get_logger(__name__)

# Mapping of contract type names to postgres type patterns
TYPE_MAP: dict[str, set[str]] = {
    "uuid": {"uuid"},
    "text": {"text", "character varying", "varchar"},
    "varchar": {"text", "character varying", "varchar"},
    "integer": {"integer", "int", "int4", "bigint", "int8", "smallint", "int2"},
    "bigint": {"bigint", "int8"},
    "numeric": {"numeric", "decimal"},
    "decimal": {"numeric", "decimal"},
    "boolean": {"boolean", "bool"},
    "timestamp": {"timestamp without time zone", "timestamp with time zone"},
    "timestamptz": {"timestamp with time zone"},
    "date": {"date"},
    "jsonb": {"jsonb"},
    "json": {"json", "jsonb"},
    "float": {"double precision", "real", "float4", "float8"},
    "double": {"double precision", "float8"},
}


async def validate_schema(
    pool: asyncpg.Pool, version: ContractVersion
) -> list[Violation]:
    """Validate actual DB schema against contract schema spec."""
    violations: list[Violation] = []
    schema_spec = version.schema_spec
    table_name = schema_spec.get("table", "")
    schema_name = schema_spec.get("schema", "public")
    columns_spec: dict[str, Any] = schema_spec.get("columns", {})

    if not table_name:
        log.warning("no_table_in_schema_spec", version_id=str(version.id))
        return violations

    # Fetch actual columns from information_schema
    actual_columns = await _fetch_actual_columns(pool, schema_name, table_name)

    if not actual_columns:
        violations.append(
            Violation(
                contract_id=version.contract_id,
                version_id=version.id,
                violation_type=ViolationType.schema_mismatch,
                severity=ViolationSeverity.critical,
                dataset=table_name,
                message=f"Table {schema_name}.{table_name} does not exist or has no columns",
            )
        )
        return violations

    actual_col_names = {col["column_name"] for col in actual_columns}
    actual_col_map = {col["column_name"]: col for col in actual_columns}

    for col_name, col_spec in columns_spec.items():
        # Check column exists
        if col_name not in actual_col_names:
            violations.append(
                Violation(
                    contract_id=version.contract_id,
                    version_id=version.id,
                    violation_type=ViolationType.schema_mismatch,
                    severity=ViolationSeverity.error,
                    dataset=table_name,
                    field_name=col_name,
                    expected="column exists",
                    actual="column missing",
                    message=f"Required column '{col_name}' not found in {table_name}",
                )
            )
            continue

        actual_col = actual_col_map[col_name]

        # Check type matches
        expected_type = col_spec.get("type", "").lower()
        actual_type = actual_col["data_type"].lower()
        if expected_type and not _types_compatible(expected_type, actual_type):
            violations.append(
                Violation(
                    contract_id=version.contract_id,
                    version_id=version.id,
                    violation_type=ViolationType.schema_mismatch,
                    severity=ViolationSeverity.error,
                    dataset=table_name,
                    field_name=col_name,
                    expected=expected_type,
                    actual=actual_type,
                    message=(
                        f"Column '{col_name}' type mismatch: "
                        f"expected {expected_type}, got {actual_type}"
                    ),
                )
            )

        # Check nullable constraint
        if col_spec.get("nullable") is False and actual_col["is_nullable"] == "YES":
            violations.append(
                Violation(
                    contract_id=version.contract_id,
                    version_id=version.id,
                    violation_type=ViolationType.schema_mismatch,
                    severity=ViolationSeverity.warning,
                    dataset=table_name,
                    field_name=col_name,
                    expected="NOT NULL",
                    actual="NULLABLE",
                    message=f"Column '{col_name}' should be NOT NULL",
                )
            )

    log.info(
        "schema_validated",
        table=table_name,
        violation_count=len(violations),
    )
    return violations


async def _fetch_actual_columns(
    pool: asyncpg.Pool, schema_name: str, table_name: str
) -> list[dict[str, Any]]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = $1 AND table_name = $2
            ORDER BY ordinal_position
            """,
            schema_name,
            table_name,
        )
    return [dict(row) for row in rows]


def _types_compatible(expected: str, actual: str) -> bool:
    allowed = TYPE_MAP.get(expected)
    if allowed is None:
        return expected in actual or actual in expected
    return actual in allowed
