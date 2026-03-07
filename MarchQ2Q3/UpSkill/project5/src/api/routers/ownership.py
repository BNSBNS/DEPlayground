from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from src.db.pool import get_pool
from src.governance.ownership import (
    get_dataset_consumers,
    get_dataset_owner,
    get_ownership_summary,
    get_team_datasets,
)
from src.logging import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/ownership", tags=["ownership"])


@router.get("")
async def ownership_overview(
    dataset: str | None = Query(None),
    team: str | None = Query(None),
) -> dict[str, Any]:
    pool = await get_pool()

    if dataset:
        owner = await get_dataset_owner(pool, dataset)
        consumers = await get_dataset_consumers(pool, dataset)
        result: dict[str, Any] = {
            "dataset": dataset,
            "owner": _serialize(owner),
            "consumers": consumers,
        }
        return result

    if team:
        datasets = await get_team_datasets(pool, team)
        return {"team": team, "datasets": [_serialize(d) for d in datasets]}

    return _serialize(await get_ownership_summary(pool))


def _serialize(obj: Any) -> Any:
    if obj is None:
        return None
    if isinstance(obj, dict):
        return {
            k: str(v) if hasattr(v, "hex") or hasattr(v, "isoformat") else v
            for k, v in obj.items()
        }
    return obj
