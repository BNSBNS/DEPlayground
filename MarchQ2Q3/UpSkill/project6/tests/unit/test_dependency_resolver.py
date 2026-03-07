from __future__ import annotations

import pytest

from src.models.features import FeatureDefinition, ValueType
from src.registry.dependency_resolver import (
    CircularDependencyError,
    build_dependency_graph,
    detect_circular_dependencies,
    resolve_computation_order,
    topological_sort,
)


def _make_feature(name: str, transform: str | None = None) -> FeatureDefinition:
    return FeatureDefinition(
        name=name,
        feature_set="test",
        entity="customer",
        value_type=ValueType.FLOAT64,
        transform=transform,
    )


class TestBuildDependencyGraph:
    def test_no_dependencies(self) -> None:
        features = [_make_feature("a"), _make_feature("b")]
        graph = build_dependency_graph(features)
        assert graph == {"a": [], "b": []}

    def test_with_ref_dependency(self) -> None:
        features = [
            _make_feature("a"),
            _make_feature("b", transform="ref:a"),
        ]
        graph = build_dependency_graph(features)
        assert graph["b"] == ["a"]
        assert graph["a"] == []

    def test_chain_dependencies(self) -> None:
        features = [
            _make_feature("a"),
            _make_feature("b", transform="ref:a"),
            _make_feature("c", transform="ref:b"),
        ]
        graph = build_dependency_graph(features)
        assert graph["c"] == ["b"]
        assert graph["b"] == ["a"]


class TestTopologicalSort:
    def test_empty_graph(self) -> None:
        assert topological_sort({}) == []

    def test_single_node(self) -> None:
        result = topological_sort({"a": []})
        assert result == ["a"]

    def test_linear_chain(self) -> None:
        graph = {"a": [], "b": ["a"], "c": ["b"]}
        result = topological_sort(graph)
        assert result.index("a") < result.index("b")
        assert result.index("b") < result.index("c")

    def test_diamond_dependency(self) -> None:
        graph = {"a": [], "b": ["a"], "c": ["a"], "d": ["b", "c"]}
        result = topological_sort(graph)
        assert result.index("a") < result.index("b")
        assert result.index("a") < result.index("c")
        assert result.index("b") < result.index("d")
        assert result.index("c") < result.index("d")

    def test_independent_nodes(self) -> None:
        graph = {"a": [], "b": [], "c": []}
        result = topological_sort(graph)
        assert set(result) == {"a", "b", "c"}

    def test_circular_dependency_raises(self) -> None:
        graph = {"a": ["b"], "b": ["c"], "c": ["a"]}
        with pytest.raises(CircularDependencyError) as exc_info:
            topological_sort(graph)
        assert len(exc_info.value.cycle) >= 2

    def test_self_reference_raises(self) -> None:
        graph = {"a": ["a"]}
        with pytest.raises(CircularDependencyError):
            topological_sort(graph)


class TestDetectCircularDependencies:
    def test_no_cycle(self) -> None:
        graph = {"a": [], "b": ["a"]}
        assert detect_circular_dependencies(graph) is None

    def test_has_cycle(self) -> None:
        graph = {"a": ["b"], "b": ["a"]}
        cycle = detect_circular_dependencies(graph)
        assert cycle is not None
        assert len(cycle) >= 2


class TestResolveComputationOrder:
    def test_respects_dependencies(self) -> None:
        features = [
            _make_feature("c", transform="ref:b"),
            _make_feature("b", transform="ref:a"),
            _make_feature("a"),
        ]
        order = resolve_computation_order(features)
        assert order.index("a") < order.index("b")
        assert order.index("b") < order.index("c")

    def test_independent_features(self) -> None:
        features = [_make_feature("x"), _make_feature("y"), _make_feature("z")]
        order = resolve_computation_order(features)
        assert set(order) == {"x", "y", "z"}
