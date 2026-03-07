"""Query and graph exploration endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from src.ingestion.store import store
from src.models.retrieval import QueryResponse

router = APIRouter(tags=["query"])


class QueryRequest(BaseModel):
    question: str


@router.post("/query", response_model=QueryResponse)
async def query(body: QueryRequest) -> QueryResponse:
    """Answer a natural-language question using the QueryEngine."""
    # Import lazily to avoid circular deps and allow graceful fallback
    try:
        from src.reasoning.engine import get_query_engine

        engine = get_query_engine()
        return await engine.run(body.question)
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="QueryEngine not available — reasoning module not installed",
        )


@router.get("/graph/node/{node_id}")
async def get_node(node_id: str) -> dict[str, Any]:
    """Return node details and immediate neighbors."""
    node = store.nodes.get(node_id)
    if node is None:
        raise HTTPException(status_code=404, detail=f"Node {node_id} not found")

    neighbors: list[dict[str, Any]] = []
    for edge in store.edges:
        if edge["source_id"] == node_id:
            target = store.nodes.get(edge["target_id"])
            if target:
                neighbors.append({
                    "node": target,
                    "relationship": edge["relationship"],
                    "direction": "outgoing",
                })
        elif edge["target_id"] == node_id:
            source = store.nodes.get(edge["source_id"])
            if source:
                neighbors.append({
                    "node": source,
                    "relationship": edge["relationship"],
                    "direction": "incoming",
                })

    return {"node": node, "neighbors": neighbors}


@router.get("/graph/lineage/{table}")
async def get_lineage(
    table: str,
    direction: str = Query(default="both", pattern="^(upstream|downstream|both)$"),
    depth: int = Query(default=3, ge=1, le=10),
) -> dict[str, Any]:
    """Return upstream and/or downstream lineage for a table."""
    upstream = _traverse(table, "upstream", depth) if direction in ("upstream", "both") else []
    downstream = (
        _traverse(table, "downstream", depth) if direction in ("downstream", "both") else []
    )
    return {"table": table, "upstream": upstream, "downstream": downstream}


def _traverse(start_id: str, direction: str, max_depth: int) -> list[dict[str, Any]]:
    """BFS traversal through graph edges."""
    visited: set[str] = set()
    queue: list[tuple[str, int]] = [(start_id, 0)]
    results: list[dict[str, Any]] = []

    while queue:
        current_id, current_depth = queue.pop(0)
        if current_id in visited or current_depth > max_depth:
            continue
        visited.add(current_id)

        for edge in store.edges:
            if direction == "upstream" and edge["target_id"] == current_id:
                neighbor_id = edge["source_id"]
            elif direction == "downstream" and edge["source_id"] == current_id:
                neighbor_id = edge["target_id"]
            else:
                continue

            if neighbor_id not in visited:
                node = store.nodes.get(neighbor_id)
                if node:
                    results.append({
                        "node": node,
                        "relationship": edge["relationship"],
                        "depth": current_depth + 1,
                    })
                    queue.append((neighbor_id, current_depth + 1))

    return results


@router.get("/graph/search")
async def search_nodes(
    q: str = Query(min_length=1, description="Search query"),
) -> list[dict[str, Any]]:
    """Search nodes by name (case-insensitive substring match)."""
    query_lower = q.lower()
    return [
        node
        for node in store.nodes.values()
        if query_lower in node.get("name", "").lower()
        or query_lower in node.get("description", "").lower()
    ]
