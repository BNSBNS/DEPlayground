from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.contracts.differ import diff_versions
from src.contracts.registry import (
    create_contract,
    create_version,
    get_contract,
    get_version_by_semver,
    list_contracts,
    list_versions,
)
from src.contracts.version_manager import compute_next_version
from src.db.pool import get_pool
from src.governance.audit import record_audit
from src.logging import get_logger
from src.models.contracts import Contract, ContractStatus
from src.models.versions import ContractVersion

log = get_logger(__name__)

router = APIRouter(prefix="/contracts", tags=["contracts"])


class CreateContractRequest(BaseModel):
    name: str
    dataset: str
    owner_team: str
    owner_contact: str
    status: ContractStatus = ContractStatus.draft
    schema_spec: dict[str, Any] = Field(default_factory=dict)
    quality_spec: dict[str, Any] = Field(default_factory=dict)
    sla_spec: dict[str, Any] = Field(default_factory=dict)
    consumers: list[str] = Field(default_factory=list)
    changelog: str = "Initial version"


class CreateVersionRequest(BaseModel):
    schema_spec: dict[str, Any] = Field(default_factory=dict)
    quality_spec: dict[str, Any] = Field(default_factory=dict)
    sla_spec: dict[str, Any] = Field(default_factory=dict)
    consumers: list[str] = Field(default_factory=list)
    changelog: str = ""
    auto_version: bool = True  # auto-compute semver bump


@router.get("")
async def list_all_contracts(
    status: ContractStatus | None = None,
    owner_team: str | None = None,
) -> list[dict[str, Any]]:
    pool = await get_pool()
    contracts = await list_contracts(pool, status=status, owner_team=owner_team)
    return [c.model_dump(mode="json") for c in contracts]


@router.post("", status_code=201)
async def create_new_contract(req: CreateContractRequest) -> dict[str, Any]:
    pool = await get_pool()

    contract = Contract(
        name=req.name,
        dataset=req.dataset,
        owner_team=req.owner_team,
        owner_contact=req.owner_contact,
        status=req.status,
    )

    version = ContractVersion(
        contract_id=contract.id,
        version="1.0.0",
        schema_spec=req.schema_spec,
        quality_spec=req.quality_spec,
        sla_spec=req.sla_spec,
        consumers=req.consumers,
        changelog=req.changelog,
    )
    contract.current_version_id = version.id

    await create_contract(pool, contract)
    await create_version(pool, version)
    await record_audit(
        pool, "contract", contract.id, "created", req.owner_team,
        {"name": req.name, "dataset": req.dataset},
    )

    return contract.model_dump(mode="json")


@router.get("/{contract_id}")
async def get_single_contract(contract_id: uuid.UUID) -> dict[str, Any]:
    pool = await get_pool()
    contract = await get_contract(pool, contract_id)
    if contract is None:
        raise HTTPException(status_code=404, detail="Contract not found")
    return contract.model_dump(mode="json")


@router.post("/{contract_id}/versions", status_code=201)
async def publish_version(
    contract_id: uuid.UUID, req: CreateVersionRequest
) -> dict[str, Any]:
    pool = await get_pool()
    contract = await get_contract(pool, contract_id)
    if contract is None:
        raise HTTPException(status_code=404, detail="Contract not found")

    versions = await list_versions(pool, contract_id)

    if req.auto_version and versions:
        latest = versions[0]
        new_spec = {
            "schema": req.schema_spec,
            "quality": req.quality_spec,
            "sla": req.sla_spec,
        }
        next_ver, bump = compute_next_version(latest, new_spec)
    else:
        next_ver = "1.0.0" if not versions else req.changelog
        bump = "initial"
        if versions:
            # Fallback: just increment patch
            parts = versions[0].version.split(".")
            next_ver = f"{parts[0]}.{parts[1]}.{int(parts[2]) + 1}"

    version = ContractVersion(
        contract_id=contract_id,
        version=next_ver,
        schema_spec=req.schema_spec,
        quality_spec=req.quality_spec,
        sla_spec=req.sla_spec,
        consumers=req.consumers,
        changelog=req.changelog,
    )

    await create_version(pool, version)
    await record_audit(
        pool, "contract_version", version.id, "published", contract.owner_team,
        {"version": next_ver, "bump": bump},
    )

    return version.model_dump(mode="json")


@router.get("/{contract_id}/versions")
async def get_versions(contract_id: uuid.UUID) -> list[dict[str, Any]]:
    pool = await get_pool()
    versions = await list_versions(pool, contract_id)
    return [v.model_dump(mode="json") for v in versions]


@router.get("/{contract_id}/diff/{v1}/{v2}")
async def diff_contract_versions(
    contract_id: uuid.UUID, v1: str, v2: str
) -> dict[str, Any]:
    pool = await get_pool()
    ver1 = await get_version_by_semver(pool, contract_id, v1)
    ver2 = await get_version_by_semver(pool, contract_id, v2)

    if ver1 is None:
        raise HTTPException(status_code=404, detail=f"Version {v1} not found")
    if ver2 is None:
        raise HTTPException(status_code=404, detail=f"Version {v2} not found")

    return diff_versions(ver1, ver2)
