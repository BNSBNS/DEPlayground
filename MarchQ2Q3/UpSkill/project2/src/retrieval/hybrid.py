"""Hybrid search: merge vector + graph retrieval with reciprocal rank fusion."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from src.logging import get_logger
from src.models.retrieval import RetrievalResult
from src.retrieval.graph import expand_neighbors, text_search
from src.retrieval.vector import vector_search

if TYPE_CHECKING:
    import asyncpg

    from src.ingestion.store import IngestionStore

logger = get_logger("retrieval.hybrid")

# RRF constant (standard value from the literature)
_RRF_K = 60


async def hybrid_search(
    pool: asyncpg.Pool,  # type: ignore[type-arg]
    store: IngestionStore,
    query: str,
    vector_weight: float = 0.6,
    graph_weight: float = 0.4,
    top_k: int = 10,
) -> list[RetrievalResult]:
    """Run vector + graph retrieval and merge via reciprocal rank fusion."""
    # Phase 1: vector search and graph text search in parallel
    vec_results, graph_text_results = await asyncio.gather(
        vector_search(pool, query, top_k=top_k),
        text_search(store, query, limit=top_k),
    )

    # Phase 2: graph expansion from top vector hits
    seed_ids = [
        r.metadata["entity_id"]
        for r in vec_results[:5]
        if r.metadata.get("entity_id")
    ]
    graph_expanded = (
        await expand_neighbors(store, seed_ids, hops=2) if seed_ids else []
    )

    # Merge all graph results
    all_graph = graph_text_results + graph_expanded

    # Build rank maps (1-indexed)
    vec_rank: dict[str, int] = {}
    for rank, r in enumerate(vec_results, start=1):
        key = r.content
        if key not in vec_rank:
            vec_rank[key] = rank

    graph_rank: dict[str, int] = {}
    for rank, r in enumerate(all_graph, start=1):
        key = r.content
        if key not in graph_rank:
            graph_rank[key] = rank

    # Deduplicate by content, keeping best metadata
    seen: dict[str, RetrievalResult] = {}
    for r in vec_results + all_graph:
        if r.content not in seen:
            seen[r.content] = r

    # Compute fused scores
    scored: list[tuple[float, RetrievalResult]] = []
    for content, result in seen.items():
        v_score = vector_weight / (vec_rank[content] + _RRF_K) if content in vec_rank else 0.0
        g_score = graph_weight / (graph_rank[content] + _RRF_K) if content in graph_rank else 0.0
        fused = v_score + g_score

        fused_result = result.model_copy(update={"score": fused})
        scored.append((fused, fused_result))

    scored.sort(key=lambda t: t[0], reverse=True)
    final = [r for _, r in scored[:top_k]]

    logger.debug(
        "hybrid_search_complete",
        query=query[:80],
        vector_hits=len(vec_results),
        graph_hits=len(all_graph),
        fused=len(final),
    )
    return final
