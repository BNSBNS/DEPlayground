from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from src.api.errors import FeatureNotFoundError
from src.models.features import FeatureDefinition, FeatureStatus, ValueType

router = APIRouter(prefix="/features", tags=["features"])


class FeatureCreateRequest(BaseModel):
    name: str
    feature_set: str
    entity: str
    value_type: ValueType
    description: str = ""
    owner: str = ""
    tags: list[str] = []
    batch_source: str | None = None
    stream_source: str | None = None
    freshness_sla_minutes: int = 60


class FeatureUpdateRequest(BaseModel):
    description: str | None = None
    owner: str | None = None
    tags: list[str] | None = None
    status: FeatureStatus | None = None
    freshness_sla_minutes: int | None = None


class BackfillRequest(BaseModel):
    start_date: datetime | None = None
    end_date: datetime | None = None
    days: int = 90


@router.get("")
async def list_features(
    entity: str | None = None,
    feature_set: str | None = None,
    status: str | None = None,
    search: str | None = None,
    owner: str | None = None,
    tag: str | None = None,
) -> dict[str, Any]:
    from src.api.main import get_catalog

    catalog = get_catalog()
    if search:
        features = await catalog.search_features(search, owner=owner, tag=tag)
    else:
        features = await catalog.list_features(
            entity=entity, feature_set=feature_set, status=status
        )
    return {"features": [f.model_dump() for f in features], "count": len(features)}


@router.post("", status_code=201)
async def create_feature(req: FeatureCreateRequest) -> dict[str, Any]:
    from src.api.main import get_catalog

    catalog = get_catalog()
    feature = FeatureDefinition(**req.model_dump())
    created = await catalog.create_feature(feature)
    return {"feature": created.model_dump()}


@router.get("/{name}")
async def get_feature(name: str) -> dict[str, Any]:
    from src.api.main import get_catalog

    catalog = get_catalog()
    feature = await catalog.get_feature(name)
    if feature is None:
        raise FeatureNotFoundError(name)
    return {"feature": feature.model_dump()}


@router.put("/{name}")
async def update_feature(name: str, req: FeatureUpdateRequest) -> dict[str, Any]:
    from src.api.main import get_catalog

    catalog = get_catalog()
    existing = await catalog.get_feature(name)
    if existing is None:
        raise FeatureNotFoundError(name)

    updates = req.model_dump(exclude_none=True)
    updated = existing.model_copy(update=updates)
    saved = await catalog.create_feature(updated)
    return {"feature": saved.model_dump()}


@router.post("/{name}/backfill")
async def trigger_backfill(name: str, req: BackfillRequest) -> dict[str, Any]:
    from src.api.main import get_catalog, get_batch_engine

    catalog = get_catalog()
    feature = await catalog.get_feature(name)
    if feature is None:
        raise FeatureNotFoundError(name)

    fs = await catalog.get_feature_set(feature.feature_set)
    if fs is None:
        raise HTTPException(status_code=404, detail="Feature set not found")

    end = req.end_date or datetime.utcnow()
    start = req.start_date or (end - timedelta(days=req.days))

    from src.compute.batch.backfill import BackfillJob

    engine = get_batch_engine()
    job = BackfillJob(engine)
    rows = await job.run(fs, [feature], start, end)
    return {"status": "complete", "rows_processed": rows}
