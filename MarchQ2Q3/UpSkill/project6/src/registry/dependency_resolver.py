from __future__ import annotations

import structlog

from src.models.features import FeatureDefinition

logger = structlog.get_logger(__name__)


class CircularDependencyError(Exception):
    def __init__(self, cycle: list[str]) -> None:
        self.cycle = cycle
        super().__init__(f"Circular dependency detected: {' -> '.join(cycle)}")


def build_dependency_graph(features: list[FeatureDefinition]) -> dict[str, list[str]]:
    """Build adjacency list of feature dependencies from transform refs."""
    graph: dict[str, list[str]] = {}
    for f in features:
        deps: list[str] = []
        if f.transform and f.transform.startswith("ref:"):
            ref_name = f.transform.removeprefix("ref:")
            deps.append(ref_name)
        graph[f.name] = deps
    return graph


def topological_sort(graph: dict[str, list[str]]) -> list[str]:
    """Return features in dependency order. Raises CircularDependencyError if cycle exists."""
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {node: WHITE for node in graph}
    order: list[str] = []
    path: list[str] = []

    def dfs(node: str) -> None:
        if node not in color:
            return
        if color[node] == BLACK:
            return
        if color[node] == GRAY:
            cycle_start = path.index(node)
            raise CircularDependencyError(path[cycle_start:] + [node])

        color[node] = GRAY
        path.append(node)

        for dep in graph.get(node, []):
            dfs(dep)

        path.pop()
        color[node] = BLACK
        order.append(node)

    for node in graph:
        if color[node] == WHITE:
            dfs(node)

    return order


def detect_circular_dependencies(graph: dict[str, list[str]]) -> list[str] | None:
    """Return the cycle if one exists, else None."""
    try:
        topological_sort(graph)
        return None
    except CircularDependencyError as e:
        return e.cycle


def resolve_computation_order(features: list[FeatureDefinition]) -> list[str]:
    """Return feature names in the order they should be computed."""
    graph = build_dependency_graph(features)
    return topological_sort(graph)
