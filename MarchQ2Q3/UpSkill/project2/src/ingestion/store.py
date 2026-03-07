from __future__ import annotations

import uuid
from typing import Any

import structlog

log = structlog.get_logger(__name__)


class IngestionStore:
    """In-memory store for ingested graph data."""

    def __init__(self) -> None:
        self.nodes: dict[str, dict[str, Any]] = {}
        self.edges: list[dict[str, Any]] = []

    def add_node(
        self,
        node_id: str,
        node_type: str,
        name: str,
        **props: Any,
    ) -> dict[str, Any]:
        """Add a node to the store. Returns the node dict."""
        node = {"id": node_id, "type": node_type, "name": name, **props}
        self.nodes[node_id] = node
        log.debug("node_added", node_id=node_id, node_type=node_type, name=name)
        return node

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        relationship: str,
        **props: Any,
    ) -> dict[str, Any]:
        """Add an edge to the store. Returns the edge dict."""
        edge = {
            "id": str(uuid.uuid4()),
            "source_id": source_id,
            "target_id": target_id,
            "relationship": relationship,
            **props,
        }
        self.edges.append(edge)
        log.debug(
            "edge_added",
            source_id=source_id,
            target_id=target_id,
            relationship=relationship,
        )
        return edge

    def get_nodes_by_type(self, node_type: str) -> list[dict[str, Any]]:
        """Return all nodes matching the given type."""
        return [n for n in self.nodes.values() if n["type"] == node_type]

    def clear(self) -> None:
        """Remove all nodes and edges."""
        count = len(self.nodes) + len(self.edges)
        self.nodes.clear()
        self.edges.clear()
        log.info("store_cleared", items_removed=count)


# Module-level singleton shared across ingestors.
store = IngestionStore()
