"""In-memory lineage graph using adjacency lists."""

from collections import deque

from src.logging import get_logger

logger = get_logger(__name__)

# Module-level singleton
_graph: "LineageGraph | None" = None


class LineageGraph:
    """Directed graph for data lineage, using dict-of-sets adjacency lists."""

    def __init__(self) -> None:
        self._upstream: dict[str, set[str]] = {}  # node → set of upstream nodes
        self._downstream: dict[str, set[str]] = {}  # node → set of downstream nodes

    def add_edge(self, upstream: str, downstream: str) -> None:
        """Add a directed edge: upstream feeds into downstream."""
        self._downstream.setdefault(upstream, set()).add(downstream)
        self._upstream.setdefault(downstream, set()).add(upstream)
        # Ensure both nodes exist as keys
        self._upstream.setdefault(upstream, set())
        self._downstream.setdefault(downstream, set())

    def get_upstream(self, node_id: str, max_depth: int = 10) -> set[str]:
        """BFS traversal to find all upstream dependencies."""
        return self._bfs(node_id, self._upstream, max_depth)

    def get_downstream(self, node_id: str, max_depth: int = 10) -> set[str]:
        """BFS traversal to find all downstream dependents."""
        return self._bfs(node_id, self._downstream, max_depth)

    def get_impact_summary(self, node_id: str) -> dict[str, int]:
        """Count affected downstream assets."""
        downstream = self.get_downstream(node_id)
        return {"total_affected": len(downstream)}

    def has_node(self, node_id: str) -> bool:
        """Check if a node exists in the graph."""
        return node_id in self._upstream or node_id in self._downstream

    def all_nodes(self) -> set[str]:
        """Return all nodes in the graph."""
        return set(self._upstream.keys()) | set(self._downstream.keys())

    def to_dict(self) -> dict[str, list[str]]:
        """Export graph as a dict of downstream edges."""
        return {node: sorted(deps) for node, deps in self._downstream.items()}

    def _bfs(
        self, start: str, adjacency: dict[str, set[str]], max_depth: int
    ) -> set[str]:
        """BFS from start node, collecting all reachable nodes."""
        visited: set[str] = set()
        queue: deque[tuple[str, int]] = deque([(start, 0)])

        while queue:
            node, depth = queue.popleft()
            if depth >= max_depth:
                continue
            for neighbor in adjacency.get(node, set()):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, depth + 1))

        return visited


def get_lineage_graph() -> LineageGraph:
    """Get the module-level lineage graph singleton."""
    global _graph  # noqa: PLW0603
    if _graph is None:
        _graph = LineageGraph()
    return _graph


def set_lineage_graph(graph: LineageGraph) -> None:
    """Set the module-level lineage graph (for testing/initialization)."""
    global _graph  # noqa: PLW0603
    _graph = graph
