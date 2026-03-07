"""Ingestion trigger endpoints."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.ingestion.store import store
from src.logging import get_logger

router = APIRouter(prefix="/ingestion", tags=["ingestion"])
logger = get_logger("api.ingestion")

SourceType = Literal["schema", "dbt", "dashboard", "docs", "owner"]

_INGESTOR_MAP: dict[str, str] = {
    "schema": "src.ingestion.schema_ingestor",
    "dbt": "src.ingestion.dbt_ingestor",
    "dashboard": "src.ingestion.dashboard_ingestor",
    "docs": "src.ingestion.docs_ingestor",
    "owner": "src.ingestion.owner_ingestor",
}


class IngestionRequest(BaseModel):
    source_type: SourceType


class IngestionResponse(BaseModel):
    source_type: str
    status: str
    nodes_before: int
    nodes_after: int
    edges_before: int
    edges_after: int
    nodes_added: int
    edges_added: int


@router.post("/run", response_model=IngestionResponse)
async def run_ingestion(body: IngestionRequest) -> IngestionResponse:
    """Trigger ingestion for a specific source type."""
    module_path = _INGESTOR_MAP.get(body.source_type)
    if not module_path:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown source type: {body.source_type}",
        )

    nodes_before = len(store.nodes)
    edges_before = len(store.edges)

    try:
        result = await _run_ingestor(module_path)
    except Exception as exc:
        logger.error("ingestion_failed", source_type=body.source_type, error=str(exc))
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {exc}")

    nodes_after = len(store.nodes)
    edges_after = len(store.edges)

    return IngestionResponse(
        source_type=body.source_type,
        status=result.get("status", "completed"),
        nodes_before=nodes_before,
        nodes_after=nodes_after,
        edges_before=edges_before,
        edges_after=edges_after,
        nodes_added=nodes_after - nodes_before,
        edges_added=edges_after - edges_before,
    )


async def _run_ingestor(module_path: str) -> dict[str, Any]:
    """Dynamically import and run an ingestor module's ``run`` function."""
    import importlib

    module = importlib.import_module(module_path)
    run_fn = getattr(module, "run", None)
    if run_fn is None:
        raise AttributeError(f"Module {module_path} has no 'run' function")
    return await run_fn()  # type: ignore[no-any-return]
