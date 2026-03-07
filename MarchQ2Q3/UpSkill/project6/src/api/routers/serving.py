from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/serve", tags=["serving"])


class OnlineRequest(BaseModel):
    entity_keys: list[str]
    feature_names: list[str]


class TrainingRequest(BaseModel):
    name: str
    entity_type: str
    entity_keys: list[str]
    feature_names: list[str]
    timestamps: list[str] | None = None
    start_time: str | None = None
    end_time: str | None = None


@router.post("/online")
async def serve_online(req: OnlineRequest) -> dict[str, Any]:
    from src.api.main import get_online_service

    service = get_online_service()
    results = await service.get_features_multi(req.entity_keys, req.feature_names)
    return {
        "results": [r.to_dict() for r in results],
        "count": len(results),
    }


@router.post("/training")
async def serve_training(req: TrainingRequest) -> dict[str, Any]:
    from src.api.main import get_training_builder

    builder = get_training_builder()

    timestamps = None
    if req.timestamps:
        timestamps = [datetime.fromisoformat(t) for t in req.timestamps]

    start = datetime.fromisoformat(req.start_time) if req.start_time else None
    end = datetime.fromisoformat(req.end_time) if req.end_time else None

    dataset, rows = await builder.build(
        name=req.name,
        entity_type=req.entity_type,
        entity_keys=req.entity_keys,
        feature_names=req.feature_names,
        timestamps=timestamps,
        start_time=start,
        end_time=end,
    )

    return {
        "dataset": dataset.model_dump(mode="json"),
        "rows": rows[:100],  # limit response size
        "total_rows": len(rows),
    }
