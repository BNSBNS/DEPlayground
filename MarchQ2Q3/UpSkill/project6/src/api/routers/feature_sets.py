from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from src.api.errors import FeatureSetNotFoundError
from src.models.features import FeatureSet

router = APIRouter(prefix="/feature-sets", tags=["feature-sets"])


class FeatureSetCreateRequest(BaseModel):
    name: str
    entity: str
    features: list[str] = []
    batch_source: str | None = None
    stream_source: str | None = None
    schedule: str = "daily"


@router.get("")
async def list_feature_sets() -> dict[str, Any]:
    from src.api.main import get_catalog

    catalog = get_catalog()
    sets = await catalog.list_feature_sets()
    return {"feature_sets": [fs.model_dump() for fs in sets], "count": len(sets)}


@router.post("", status_code=201)
async def create_feature_set(req: FeatureSetCreateRequest) -> dict[str, Any]:
    from src.api.main import get_catalog

    catalog = get_catalog()
    fs = FeatureSet(**req.model_dump())
    created = await catalog.create_feature_set(fs)
    return {"feature_set": created.model_dump()}


@router.get("/{name}")
async def get_feature_set(name: str) -> dict[str, Any]:
    from src.api.main import get_catalog

    catalog = get_catalog()
    fs = await catalog.get_feature_set(name)
    if fs is None:
        raise FeatureSetNotFoundError(name)
    return {"feature_set": fs.model_dump()}
