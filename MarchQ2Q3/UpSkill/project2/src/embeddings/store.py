"""pgvector storage for entity embeddings."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import asyncpg


async def upsert_embedding(
    pool: asyncpg.Pool,
    entity_id: str,
    entity_type: str,
    content: str,
    embedding: list[float],
    metadata: dict | None = None,
) -> None:
    """Insert or update an embedding for an entity in pgvector."""
    vec_literal = f"[{','.join(str(v) for v in embedding)}]"
    meta_json = json.dumps(metadata) if metadata else None

    await pool.execute(
        """
        INSERT INTO embeddings (entity_id, entity_type, content, embedding, metadata)
        VALUES ($1, $2, $3, $4::vector, $5::jsonb)
        ON CONFLICT (entity_id)
        DO UPDATE SET
            entity_type = EXCLUDED.entity_type,
            content     = EXCLUDED.content,
            embedding   = EXCLUDED.embedding,
            metadata    = EXCLUDED.metadata,
            updated_at  = now()
        """,
        entity_id,
        entity_type,
        content,
        vec_literal,
        meta_json,
    )


async def search_similar(
    pool: asyncpg.Pool,
    query_embedding: list[float],
    top_k: int = 5,
    entity_type: str | None = None,
) -> list[dict]:
    """Find the top-k most similar embeddings using cosine distance (<=>)."""
    vec_literal = f"[{','.join(str(v) for v in query_embedding)}]"

    if entity_type:
        rows = await pool.fetch(
            """
            SELECT entity_id, entity_type, content, metadata,
                   1 - (embedding <=> $1::vector) AS score
            FROM embeddings
            WHERE entity_type = $2
            ORDER BY embedding <=> $1::vector
            LIMIT $3
            """,
            vec_literal,
            entity_type,
            top_k,
        )
    else:
        rows = await pool.fetch(
            """
            SELECT entity_id, entity_type, content, metadata,
                   1 - (embedding <=> $1::vector) AS score
            FROM embeddings
            ORDER BY embedding <=> $1::vector
            LIMIT $2
            """,
            vec_literal,
            top_k,
        )

    return [dict(row) for row in rows]


async def delete_embeddings(pool: asyncpg.Pool, entity_id: str) -> None:
    """Delete all embeddings for a given entity."""
    await pool.execute("DELETE FROM embeddings WHERE entity_id = $1", entity_id)
