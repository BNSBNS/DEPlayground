"""Batch-index graph entities into pgvector."""

from __future__ import annotations

import structlog
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import asyncpg

    from src.ingestion.store import IngestionStore

from src.embeddings.embedder import get_embedder
from src.embeddings.store import upsert_embedding

logger = structlog.get_logger(__name__)


def _build_description(node: dict) -> str:
    """Build a text description from node properties for embedding."""
    parts: list[str] = []
    if name := node.get("name"):
        parts.append(str(name))
    if desc := node.get("description"):
        parts.append(str(desc))
    # Include other meaningful text properties
    for key in ("owner", "tags", "sql", "query", "documentation"):
        if val := node.get(key):
            parts.append(f"{key}: {val}")
    return " | ".join(parts) if parts else ""


async def index_entities(
    pool: asyncpg.Pool,
    store: IngestionStore,
) -> dict[str, int]:
    """Embed and upsert all nodes from the IngestionStore into pgvector.

    Returns a dict mapping entity_type -> count of indexed entities.
    """
    embedder = get_embedder()
    counts: dict[str, int] = {}

    for node in store.nodes.values():
        entity_type = node.get("type", "unknown")
        entity_id = node.get("id", "")
        if not entity_id:
            continue

        description = _build_description(node)
        if not description.strip():
            continue

        embedding = await embedder.embed(description)
        await upsert_embedding(
            pool,
            entity_id=entity_id,
            entity_type=entity_type,
            content=description,
            embedding=embedding,
            metadata={"name": node.get("name", ""), "type": entity_type},
        )
        counts[entity_type] = counts.get(entity_type, 0) + 1

    logger.info("entity_indexing_complete", counts=counts)
    return counts
