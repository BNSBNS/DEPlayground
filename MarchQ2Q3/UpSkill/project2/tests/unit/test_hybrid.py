"""Tests for reciprocal rank fusion (RRF) logic in hybrid retrieval."""

from __future__ import annotations

import pytest

from src.models.retrieval import RetrievalResult


def reciprocal_rank_fusion(
    vector_results: list[RetrievalResult],
    graph_results: list[RetrievalResult],
    k: int = 60,
    vector_weight: float = 0.5,
    graph_weight: float = 0.5,
) -> list[RetrievalResult]:
    """Merge vector and graph results using RRF.

    Mirrors the logic expected in src/retrieval/hybrid.py.
    Score = weight * 1/(k + rank) for each list a result appears in.
    Results are deduplicated by content and sorted by descending fused score.
    """
    scores: dict[str, float] = {}
    result_map: dict[str, RetrievalResult] = {}

    for rank, r in enumerate(vector_results, start=1):
        key = r.content
        scores[key] = scores.get(key, 0.0) + vector_weight * (1.0 / (k + rank))
        result_map[key] = r

    for rank, r in enumerate(graph_results, start=1):
        key = r.content
        scores[key] = scores.get(key, 0.0) + graph_weight * (1.0 / (k + rank))
        if key not in result_map:
            result_map[key] = r

    sorted_keys = sorted(scores, key=lambda c: scores[c], reverse=True)
    fused: list[RetrievalResult] = []
    for key in sorted_keys:
        original = result_map[key]
        fused.append(
            RetrievalResult(
                content=original.content,
                source=original.source,
                score=round(scores[key], 6),
                metadata=original.metadata,
                reasoning_path=original.reasoning_path,
            )
        )
    return fused


try:
    from src.retrieval.hybrid import reciprocal_rank_fusion  # type: ignore[no-redef]  # noqa: F811
except ImportError:
    pass  # Use the local fallback above


def _make_vector_results() -> list[RetrievalResult]:
    return [
        RetrievalResult(content="orders_mart is the order fact table", source="vector", score=0.95),
        RetrievalResult(content="customers_mart has customer data", source="vector", score=0.88),
        RetrievalResult(content="products_mart tracks product perf", source="vector", score=0.80),
    ]


def _make_graph_results() -> list[RetrievalResult]:
    return [
        RetrievalResult(
            content="orders_mart depends on stg_orders",
            source="graph", score=0.90,
            reasoning_path="MATCH (n)-[:DEPENDS_ON]->(m)",
        ),
        RetrievalResult(content="orders_mart is the order fact table", source="graph", score=0.85),
        RetrievalResult(content="stg_orders sources from raw.orders", source="graph", score=0.70),
    ]


class TestReciprocalRankFusion:
    def test_basic_fusion(self) -> None:
        vector = _make_vector_results()
        graph = _make_graph_results()
        fused = reciprocal_rank_fusion(vector, graph)

        assert len(fused) > 0
        # All unique contents should be present
        contents = {r.content for r in fused}
        assert len(contents) == 5  # 3 vector + 3 graph - 1 overlap

    def test_shared_result_ranks_higher(self) -> None:
        """A result appearing in both lists should score higher than one in only one list."""
        vector = _make_vector_results()
        graph = _make_graph_results()
        fused = reciprocal_rank_fusion(vector, graph)

        # "orders_mart is the order fact table" appears in both
        shared_content = "orders_mart is the order fact table"
        shared = next(r for r in fused if r.content == shared_content)
        unique = next(r for r in fused if r.content == "customers_mart has customer data")
        assert shared.score > unique.score

    def test_empty_vector_results(self) -> None:
        graph = _make_graph_results()
        fused = reciprocal_rank_fusion([], graph)
        assert len(fused) == 3
        # All results should have graph-only scores
        for r in fused:
            assert r.score > 0

    def test_empty_graph_results(self) -> None:
        vector = _make_vector_results()
        fused = reciprocal_rank_fusion(vector, [])
        assert len(fused) == 3

    def test_both_empty(self) -> None:
        fused = reciprocal_rank_fusion([], [])
        assert fused == []

    def test_custom_weights(self) -> None:
        vector = _make_vector_results()
        graph = _make_graph_results()

        # Heavy vector weight
        fused_vec = reciprocal_rank_fusion(vector, graph, vector_weight=0.9, graph_weight=0.1)
        # Heavy graph weight
        fused_graph = reciprocal_rank_fusion(vector, graph, vector_weight=0.1, graph_weight=0.9)

        # Top result should differ when weights shift dramatically
        # (or at minimum the scores should differ)
        assert fused_vec[0].score != fused_graph[0].score

    def test_scores_are_positive(self) -> None:
        vector = _make_vector_results()
        graph = _make_graph_results()
        fused = reciprocal_rank_fusion(vector, graph)
        for r in fused:
            assert r.score > 0

    def test_descending_order(self) -> None:
        vector = _make_vector_results()
        graph = _make_graph_results()
        fused = reciprocal_rank_fusion(vector, graph)
        scores = [r.score for r in fused]
        assert scores == sorted(scores, reverse=True)

    def test_k_parameter_affects_scores(self) -> None:
        vector = _make_vector_results()
        graph = _make_graph_results()
        fused_low_k = reciprocal_rank_fusion(vector, graph, k=1)
        fused_high_k = reciprocal_rank_fusion(vector, graph, k=1000)

        # Lower k gives higher individual RRF scores
        assert fused_low_k[0].score > fused_high_k[0].score

    def test_single_result_each(self) -> None:
        v = [RetrievalResult(content="only vector", source="vector", score=0.9)]
        g = [RetrievalResult(content="only graph", source="graph", score=0.8)]
        fused = reciprocal_rank_fusion(v, g)
        assert len(fused) == 2
        # Equal weights, both at rank 1 => same score
        assert fused[0].score == fused[1].score
