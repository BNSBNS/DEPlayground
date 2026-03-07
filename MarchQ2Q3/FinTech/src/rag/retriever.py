"""Retriever — embed query, search vector store, return ranked results."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.rag.embedder import Embedder, MockEmbedder

if TYPE_CHECKING:
    from src.rag.vector_store import VectorStore


@dataclass
class RetrievedChunk:
    """A retrieved chunk with relevance metadata."""

    text: str
    doc_name: str
    section: str
    score: float  # cosine similarity (1.0 = identical)
    metadata: dict


class Retriever:
    """Embed queries and retrieve relevant chunks from the vector store."""

    def __init__(
        self,
        vector_store: VectorStore,
        embedder: Embedder | MockEmbedder | None = None,
    ) -> None:
        self.vector_store = vector_store
        self.embedder = embedder or MockEmbedder()

    def retrieve(
        self,
        query: str,
        n_results: int = 5,
        where: dict | None = None,
    ) -> list[RetrievedChunk]:
        """Retrieve top-k chunks relevant to the query."""
        query_vec = self.embedder.embed_query(query)
        results = self.vector_store.query(
            query_embedding=query_vec,
            n_results=n_results,
            where=where,
        )

        chunks: list[RetrievedChunk] = []
        if not results["documents"] or not results["documents"][0]:
            return chunks

        docs = results["documents"][0]
        metadatas = results["metadatas"][0]
        distances = results["distances"][0]

        for doc, meta, dist in zip(docs, metadatas, distances, strict=False):
            # ChromaDB returns cosine distance; convert to similarity
            score = 1.0 - dist
            chunks.append(
                RetrievedChunk(
                    text=doc,
                    doc_name=meta.get("doc_name", ""),
                    section=meta.get("section", ""),
                    score=score,
                    metadata=meta,
                )
            )

        return chunks
