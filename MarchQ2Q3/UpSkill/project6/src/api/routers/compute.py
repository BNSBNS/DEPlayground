from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/compute", tags=["compute"])

# Simple in-memory job tracking
_job_statuses: dict[str, dict[str, Any]] = {}


class BatchTriggerRequest(BaseModel):
    feature_set: str


@router.post("/batch/trigger")
async def trigger_batch(req: BatchTriggerRequest) -> dict[str, Any]:
    from src.api.main import get_catalog, get_batch_engine

    catalog = get_catalog()
    fs = await catalog.get_feature_set(req.feature_set)
    if fs is None:
        raise HTTPException(status_code=404, detail=f"Feature set '{req.feature_set}' not found")

    features = await catalog.list_features(feature_set=req.feature_set)
    engine = get_batch_engine()

    import uuid
    from datetime import datetime

    job_id = str(uuid.uuid4())[:8]
    _job_statuses[job_id] = {
        "job_id": job_id,
        "feature_set": req.feature_set,
        "status": "running",
        "started_at": datetime.utcnow().isoformat(),
    }

    try:
        rows = await engine.compute_feature_set(fs, features)
        _job_statuses[job_id].update({
            "status": "complete",
            "rows_processed": rows,
            "completed_at": datetime.utcnow().isoformat(),
        })
    except Exception as e:
        _job_statuses[job_id].update({
            "status": "failed",
            "error": str(e),
        })
        raise HTTPException(status_code=500, detail=str(e))

    return _job_statuses[job_id]


@router.get("/status")
async def compute_status() -> dict[str, Any]:
    return {"jobs": list(_job_statuses.values()), "count": len(_job_statuses)}
