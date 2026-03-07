from __future__ import annotations

import json
import uuid
from datetime import datetime

import asyncpg

from src.logging import get_logger
from src.models.contracts import Contract, ContractStatus
from src.models.versions import ContractVersion

log = get_logger(__name__)


async def create_contract(pool: asyncpg.Pool, contract: Contract) -> Contract:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO contracts (id, name, dataset, owner_team, owner_contact,
                                   status, current_version_id, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """,
            contract.id,
            contract.name,
            contract.dataset,
            contract.owner_team,
            contract.owner_contact,
            contract.status.value,
            contract.current_version_id,
            contract.created_at,
            contract.updated_at,
        )
    log.info("contract_created", id=str(contract.id), name=contract.name)
    return contract


async def get_contract(pool: asyncpg.Pool, contract_id: uuid.UUID) -> Contract | None:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM contracts WHERE id = $1", contract_id
        )
    if row is None:
        return None
    return _row_to_contract(row)


async def get_contract_by_dataset(
    pool: asyncpg.Pool, dataset: str
) -> Contract | None:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM contracts WHERE dataset = $1", dataset
        )
    if row is None:
        return None
    return _row_to_contract(row)


async def list_contracts(
    pool: asyncpg.Pool,
    status: ContractStatus | None = None,
    owner_team: str | None = None,
) -> list[Contract]:
    query = "SELECT * FROM contracts WHERE 1=1"
    params: list[object] = []
    idx = 1

    if status is not None:
        query += f" AND status = ${idx}"
        params.append(status.value)
        idx += 1

    if owner_team is not None:
        query += f" AND owner_team = ${idx}"
        params.append(owner_team)
        idx += 1

    query += " ORDER BY created_at DESC"

    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *params)
    return [_row_to_contract(r) for r in rows]


async def update_contract_status(
    pool: asyncpg.Pool, contract_id: uuid.UUID, status: ContractStatus
) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE contracts SET status = $1, updated_at = $2 WHERE id = $3
            """,
            status.value,
            datetime.utcnow(),
            contract_id,
        )
    log.info("contract_status_updated", id=str(contract_id), status=status.value)


async def create_version(
    pool: asyncpg.Pool, version: ContractVersion
) -> ContractVersion:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO contract_versions
                (id, contract_id, version, schema_spec, quality_spec,
                 sla_spec, consumers, changelog, published_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """,
            version.id,
            version.contract_id,
            version.version,
            json.dumps(version.schema_spec),
            json.dumps(version.quality_spec),
            json.dumps(version.sla_spec),
            json.dumps(version.consumers),
            version.changelog,
            version.published_at,
        )
        await conn.execute(
            "UPDATE contracts SET current_version_id = $1, updated_at = $2 WHERE id = $3",
            version.id,
            datetime.utcnow(),
            version.contract_id,
        )
    log.info(
        "version_created",
        id=str(version.id),
        contract_id=str(version.contract_id),
        version=version.version,
    )
    return version


async def get_version(
    pool: asyncpg.Pool, version_id: uuid.UUID
) -> ContractVersion | None:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM contract_versions WHERE id = $1", version_id
        )
    if row is None:
        return None
    return _row_to_version(row)


async def list_versions(
    pool: asyncpg.Pool, contract_id: uuid.UUID
) -> list[ContractVersion]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM contract_versions
            WHERE contract_id = $1
            ORDER BY published_at DESC
            """,
            contract_id,
        )
    return [_row_to_version(r) for r in rows]


async def get_version_by_semver(
    pool: asyncpg.Pool, contract_id: uuid.UUID, semver: str
) -> ContractVersion | None:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT * FROM contract_versions
            WHERE contract_id = $1 AND version = $2
            """,
            contract_id,
            semver,
        )
    if row is None:
        return None
    return _row_to_version(row)


async def search_contracts(
    pool: asyncpg.Pool, query: str
) -> list[Contract]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM contracts
            WHERE name ILIKE $1 OR dataset ILIKE $1 OR owner_team ILIKE $1
            ORDER BY created_at DESC
            """,
            f"%{query}%",
        )
    return [_row_to_contract(r) for r in rows]


def _row_to_contract(row: asyncpg.Record) -> Contract:
    return Contract(
        id=row["id"],
        name=row["name"],
        dataset=row["dataset"],
        owner_team=row["owner_team"],
        owner_contact=row["owner_contact"],
        status=ContractStatus(row["status"]),
        current_version_id=row["current_version_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_to_version(row: asyncpg.Record) -> ContractVersion:
    return ContractVersion(
        id=row["id"],
        contract_id=row["contract_id"],
        version=row["version"],
        schema_spec=json.loads(row["schema_spec"])
        if isinstance(row["schema_spec"], str)
        else row["schema_spec"],
        quality_spec=json.loads(row["quality_spec"])
        if isinstance(row["quality_spec"], str)
        else row["quality_spec"],
        sla_spec=json.loads(row["sla_spec"])
        if isinstance(row["sla_spec"], str)
        else row["sla_spec"],
        consumers=json.loads(row["consumers"])
        if isinstance(row["consumers"], str)
        else row["consumers"],
        changelog=row["changelog"],
        published_at=row["published_at"],
    )
