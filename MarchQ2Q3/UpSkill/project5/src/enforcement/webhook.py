from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from src.contracts.registry import get_contract_by_dataset, get_version
from src.db.pool import get_pool
from src.enforcement.checker import enforce_contract
from src.logging import get_logger
from src.notifications.violation_alerter import alert_violations

log = get_logger(__name__)

router = APIRouter(tags=["webhooks"])


@router.post("/webhooks/enforce")
async def webhook_enforce(payload: dict[str, Any]) -> dict[str, Any]:
    """Receive a dataset identifier via webhook, run enforcement, return pass/fail."""
    dataset = payload.get("dataset")
    if not dataset:
        raise HTTPException(status_code=400, detail="Missing 'dataset' in payload")

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

    if not summary["passed"]:
        await alert_violations(contract, summary["violations"])

    log.info("webhook_enforce_complete", dataset=dataset, passed=summary["passed"])
    return {
        "dataset": dataset,
        "passed": summary["passed"],
        "total_violations": summary["total_violations"],
    }
