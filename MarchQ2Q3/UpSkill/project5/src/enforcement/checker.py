from __future__ import annotations

from typing import Any

import asyncpg

from src.enforcement.quality import check_quality
from src.enforcement.sla import check_sla
from src.ge_integration import build_expectation_suite
from src.logging import get_logger
from src.models.contracts import Contract
from src.models.versions import ContractVersion
from src.models.violations import Violation
from src.schemas.validator import validate_schema

log = get_logger(__name__)


async def enforce_contract(
    pool: asyncpg.Pool, contract: Contract, version: ContractVersion
) -> dict[str, Any]:
    """Orchestrate all checks for a contract and return summary."""
    all_violations: list[Violation] = []

    # Schema check
    schema_violations = await validate_schema(pool, version)
    all_violations.extend(schema_violations)

    # Quality check (custom SQL-based)
    quality_violations = await check_quality(pool, version)
    all_violations.extend(quality_violations)

    # Generate GE expectation suite alongside custom checks (for learning / export)
    ge_suite = build_expectation_suite(version)
    log.debug("ge_suite_generated", suite=ge_suite["expectation_suite_name"],
              expectations=len(ge_suite["expectations"]))

    # SLA check
    sla_violations = await check_sla(pool, version)
    all_violations.extend(sla_violations)

    # Persist violations
    for v in all_violations:
        await _store_violation(pool, v)

    passed = len(all_violations) == 0
    summary: dict[str, Any] = {
        "contract_id": str(contract.id),
        "dataset": contract.dataset,
        "version": version.version,
        "passed": passed,
        "total_violations": len(all_violations),
        "schema_violations": len(schema_violations),
        "quality_violations": len(quality_violations),
        "sla_violations": len(sla_violations),
        "violations": [v.model_dump(mode="json") for v in all_violations],
    }

    log.info(
        "enforcement_complete",
        dataset=contract.dataset,
        passed=passed,
        violations=len(all_violations),
    )
    return summary


async def _store_violation(pool: asyncpg.Pool, violation: Violation) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO violations
                (id, contract_id, version_id, violation_type, severity,
                 dataset, field_name, expected, actual, message, detected_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            """,
            violation.id,
            violation.contract_id,
            violation.version_id,
            violation.violation_type.value,
            violation.severity.value,
            violation.dataset,
            violation.field_name,
            violation.expected,
            violation.actual,
            violation.message,
            violation.detected_at,
        )
