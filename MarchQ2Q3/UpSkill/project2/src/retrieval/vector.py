"""Vector similarity search over pgvector embeddings."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.embeddings.embedder import get_embedder
from src.embeddings.store import search_similar
from src.logging import get_logger
from src.models.retrieval import RetrievalResult

if TYPE_CHECKING:
    import asyncpg

logger = get_logger("retrieval.vector")


async def vector_search(
    pool: asyncpg.Pool,  # type: ignore[type-arg]
    query: str,
    top_k: int = 5,
) -> list[RetrievalResult]:
    """Embed the query and retrieve the most similar documents from pgvector."""
    embedder = get_embedder()
    query_embedding = await embedder.embed(query)

    rows = await search_similar(pool, query_embedding, top_k=top_k)

    results = [
        RetrievalResult(
            content=row["content"],
            source="vector",
            score=float(row.get("score", 0.0)),
            metadata={
                "entity_id": row.get("entity_id", ""),
                "entity_type": row.get("entity_type", ""),
                **(row.get("metadata", {}) or {}),
            },
        )
        for row in rows
    ]

    logger.debug("vector_search_complete", query=query[:80], results=len(results))
    return results
