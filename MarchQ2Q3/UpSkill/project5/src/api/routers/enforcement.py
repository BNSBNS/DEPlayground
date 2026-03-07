from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from src.contracts.registry import get_contract_by_dataset, get_version
from src.db.pool import get_pool
from src.enforcement.checker import enforce_contract
from src.governance.audit import record_audit
from src.logging import get_logger
from src.notifications.violation_alerter import alert_violations

log = get_logger(__name__)

router = APIRouter(prefix="/enforce", tags=["enforcement"])


@router.post("/{dataset}")
async def enforce_dataset(dataset: str) -> dict[str, Any]:
    pool = await get_pool()
    contract = await get_contract_by_dataset(pool, dataset)
    if contract is None:
        raise HTTPException(
            status_code=404, detail=f"No contract found for dataset '{dataset}'"
        )

    if contract.current_version_id is None:
        raise HTTPException(
            status_code=400,
            detail=f"Contract '{contract.name}' has no published version",
        )

    version = await get_version(pool, contract.current_version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="Contract version not found")

    summary = await enforce_contract(pool, contract, version)

    await record_audit(
        pool, "enforcement", contract.id, "enforced", "system",
        {"dataset": dataset, "passed": summary["passed"]},
    )

    if not summary["passed"]:
        await alert_violations(contract, summary["violations"])

    return summary
