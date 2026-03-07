"""Graph-based retrieval: text search, neighbor expansion, lineage traversal."""

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING

from src.logging import get_logger
from src.models.retrieval import RetrievalResult

if TYPE_CHECKING:
    from src.ingestion.store import IngestionStore

logger = get_logger("retrieval.graph")


async def text_search(
    store: IngestionStore,
    query: str,
    limit: int = 10,
) -> list[RetrievalResult]:
    """Case-insensitive text match on node names and descriptions."""
    query_lower = query.lower()
    matches: list[RetrievalResult] = []

    for node in store.nodes.values():
        name = node.get("name", "").lower()
        description = node.get("description", "").lower()

        if query_lower in name or query_lower in description:
            content_parts = [f"{node.get('type', 'unknown')}: {node.get('name', '')}"]
            if node.get("description"):
                content_parts.append(node["description"])

            matches.append(
                RetrievalResult(
                    content=" | ".join(content_parts),
                    source="graph",
                    score=1.0 if query_lower in name else 0.5,
                    metadata={"node_id": node["id"], "node_type": node.get("type", "")},
                )
            )
            if len(matches) >= limit:
                break

    matches.sort(key=lambda r: r.score, reverse=True)
    logger.debug("text_search_complete", query=query[:80], results=len(matches))
    return matches[:limit]


async def expand_neighbors(
    store: IngestionStore,
    node_ids: list[str],
    hops: int = 2,
) -> list[RetrievalResult]:
    """N-hop expansion from seed nodes via BFS."""
    visited: set[str] = set()
    queue: deque[tuple[str, int]] = deque((nid, 0) for nid in node_ids)
    results: list[RetrievalResult] = []

    while queue:
        current_id, depth = queue.popleft()
        if current_id in visited or depth > hops:
            continue
        visited.add(current_id)

        node = store.nodes.get(current_id)
        if node is None:
            continue

        # Skip seed nodes themselves -- only collect neighbors
        if depth > 0:
            content_parts = [f"{node.get('type', 'unknown')}: {node.get('name', '')}"]
            if node.get("description"):
                content_parts.append(node["description"])

            results.append(
                RetrievalResult(
                    content=" | ".join(content_parts),
                    source="graph",
                    score=1.0 / (depth + 1),
                    metadata={
                        "node_id": node["id"],
                        "node_type": node.get("type", ""),
                        "hop_distance": depth,
                    },
                )
            )

        # Expand outgoing and incoming edges
        if depth < hops:
            for edge in store.edges:
                if edge["source_id"] == current_id:
                    queue.append((edge["target_id"], depth + 1))
                elif edge["target_id"] == current_id:
                    queue.append((edge["source_id"], depth + 1))

    logger.debug(
        "expand_neighbors_complete",
        seeds=len(node_ids),
        hops=hops,
        results=len(results),
    )
    return results


def _traverse_direction(
    store: IngestionStore,
    start_id: str,
    direction: str,
    depth: int,
) -> list[RetrievalResult]:
    """BFS traversal in a single direction (upstream or downstream)."""
    visited: set[str] = set()
    queue: deque[tuple[str, int]] = deque([(start_id, 0)])
    results: list[RetrievalResult] = []

    while queue:
        current_id, current_depth = queue.popleft()
        if current_id in visited or current_depth > depth:
            continue
        visited.add(current_id)

        node = store.nodes.get(current_id)
        if node is None:
            continue

        if current_depth > 0:
            label = "upstream" if direction == "upstream" else "downstream"
            results.append(
                RetrievalResult(
                    content=f"{label}: {node.get('type', '')} {node.get('name', '')}",
                    source="graph",
                    score=1.0 / (current_depth + 1),
                    metadata={
                        "node_id": node["id"],
                        "node_type": node.get("type", ""),
                        "direction": label,
                        "depth": current_depth,
                    },
                    reasoning_path=f"{label} hop {current_depth} from {start_id}",
                )
            )

        if current_depth < depth:
            for edge in store.edges:
                if direction == "upstream" and edge["target_id"] == current_id:
                    queue.append((edge["source_id"], current_depth + 1))
                elif direction == "downstream" and edge["source_id"] == current_id:
                    queue.append((edge["target_id"], current_depth + 1))

    return results


async def lineage_search(
    store: IngestionStore,
    table_name: str,
    direction: str = "both",
    depth: int = 3,
) -> list[RetrievalResult]:
    """Upstream/downstream lineage traversal from a named table node."""
    start_id: str | None = None
    for node in store.nodes.values():
        if node.get("name", "").lower() == table_name.lower():
            start_id = node["id"]
            break

    if start_id is None:
        logger.warning("lineage_start_not_found", table_name=table_name)
        return []

    results: list[RetrievalResult] = []

    if direction in ("upstream", "both"):
        results.extend(_traverse_direction(store, start_id, "upstream", depth))
    if direction in ("downstream", "both"):
        results.extend(_traverse_direction(store, start_id, "downstream", depth))

    logger.debug(
        "lineage_search_complete",
        table=table_name,
        direction=direction,
        results=len(results),
    )
    return results
