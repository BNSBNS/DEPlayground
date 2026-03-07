"""ChromaDB-backed vector store for RAG retrieval."""

from __future__ import annotations

from typing import TYPE_CHECKING

import chromadb

from src.config import get_settings

if TYPE_CHECKING:
    from src.data.processors.chunker import Chunk


class VectorStore:
    """Wrapper around ChromaDB for storing and querying document embeddings."""

    def __init__(
        self,
        collection_name: str = "financial_docs",
        persist_dir: str | None = None,
    ) -> None:
        settings = get_settings()
        path = persist_dir or settings.CHROMA_PERSIST_DIR
        self.client = chromadb.PersistentClient(path=path)
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def add_chunks(
        self,
        chunks: list[Chunk],
        embeddings: list[list[float]],
    ) -> None:
        """Add chunks with pre-computed embeddings to the store."""
        ids = [f"{c.doc_name}_{c.chunk_index}" for c in chunks]
        documents = [c.text for c in chunks]
        metadatas = [
            {
                "doc_name": c.doc_name,
                "section": c.section,
                "chunk_index": c.chunk_index,
                "token_count": c.token_count,
                **c.metadata,
            }
            for c in chunks
        ]
        self.collection.upsert(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )

    def query(
        self,
        query_embedding: list[float],
        n_results: int = 5,
        where: dict | None = None,
    ) -> dict:
        """Query the vector store and return results."""
        kwargs: dict = {
            "query_embeddings": [query_embedding],
            "n_results": n_results,
        }
        if where:
            kwargs["where"] = where
        return self.collection.query(**kwargs)

    @property
    def count(self) -> int:
        """Number of documents in the collection."""
        return self.collection.count()

    def reset(self) -> None:
        """Delete and recreate the collection."""
        name = self.collection.name
        metadata = self.collection.metadata
        self.client.delete_collection(name)
        self.collection = self.client.get_or_create_collection(name=name, metadata=metadata)
