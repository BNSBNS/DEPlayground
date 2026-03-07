from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter

from src.db.pool import get_pool
from src.enforcement.sla import get_sla_records
from src.logging import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/sla", tags=["sla"])


@router.get("/{contract_id}")
async def get_sla(contract_id: uuid.UUID) -> list[dict[str, Any]]:
    pool = await get_pool()
    records = await get_sla_records(pool, contract_id)
    return [r.model_dump(mode="json") for r in records]
