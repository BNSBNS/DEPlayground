from __future__ import annotations

from dataclasses import dataclass, field

import structlog

from src.models.features import FeatureDefinition

logger = structlog.get_logger(__name__)


@dataclass
class LineageNode:
    name: str
    node_type: str  # "source", "feature", "model"
    upstream: list[str] = field(default_factory=list)
    downstream: list[str] = field(default_factory=list)


class LineageGraph:
    def __init__(self) -> None:
        self._nodes: dict[str, LineageNode] = {}

    def add_feature(self, feature: FeatureDefinition) -> None:
        node = LineageNode(name=feature.name, node_type="feature")

        if feature.batch_source:
            source_key = f"source:{feature.batch_source}"
            self._ensure_node(source_key, "source")
            node.upstream.append(source_key)
            self._nodes[source_key].downstream.append(feature.name)

        if feature.stream_source:
            source_key = f"topic:{feature.stream_source}"
            self._ensure_node(source_key, "source")
            node.upstream.append(source_key)
            self._nodes[source_key].downstream.append(feature.name)

        if feature.transform and feature.transform.startswith("ref:"):
            ref_name = feature.transform.removeprefix("ref:")
            node.upstream.append(ref_name)
            if ref_name in self._nodes:
                self._nodes[ref_name].downstream.append(feature.name)

        self._nodes[feature.name] = node

    def add_model(self, model_name: str, feature_names: list[str]) -> None:
        node = LineageNode(name=model_name, node_type="model", upstream=feature_names)
        self._nodes[model_name] = node
        for fname in feature_names:
            if fname in self._nodes:
                self._nodes[fname].downstream.append(model_name)

    def get_upstream(self, name: str) -> list[str]:
        node = self._nodes.get(name)
        return node.upstream if node else []

    def get_downstream(self, name: str) -> list[str]:
        node = self._nodes.get(name)
        return node.downstream if node else []

    def impact_analysis(self, name: str) -> list[str]:
        """Find all transitively affected downstream nodes."""
        visited: set[str] = set()
        queue = [name]
        result: list[str] = []

        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            if current != name:
                result.append(current)
            for downstream in self.get_downstream(current):
                if downstream not in visited:
                    queue.append(downstream)

        return result

    def _ensure_node(self, name: str, node_type: str) -> None:
        if name not in self._nodes:
            self._nodes[name] = LineageNode(name=name, node_type=node_type)

    @property
    def nodes(self) -> dict[str, LineageNode]:
        return self._nodes
