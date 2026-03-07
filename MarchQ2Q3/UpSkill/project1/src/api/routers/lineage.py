"""Lineage API endpoints."""

from fastapi import APIRouter, Query

from src.lineage.graph import get_lineage_graph
from src.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.get("/lineage/{node_id}/upstream")
async def get_upstream(
    node_id: str, max_depth: int = Query(default=5, ge=1, le=20)
) -> dict[str, object]:
    """Get upstream dependencies for a node."""
    graph = get_lineage_graph()
    nodes = graph.get_upstream(node_id, max_depth=max_depth)
    return {"node_id": node_id, "upstream": list(nodes), "count": len(nodes)}


@router.get("/lineage/{node_id}/downstream")
async def get_downstream(
    node_id: str, max_depth: int = Query(default=5, ge=1, le=20)
) -> dict[str, object]:
    """Get downstream dependents for a node."""
    graph = get_lineage_graph()
    nodes = graph.get_downstream(node_id, max_depth=max_depth)
    return {"node_id": node_id, "downstream": list(nodes), "count": len(nodes)}


@router.get("/lineage/{node_id}/impact")
async def get_impact(node_id: str) -> dict[str, object]:
    """Get impact summary for a node — counts of affected downstream assets."""
    graph = get_lineage_graph()
    downstream = graph.get_downstream(node_id, max_depth=10)
    return {
        "node_id": node_id,
        "total_affected": len(downstream),
        "affected_nodes": list(downstream),
    }
