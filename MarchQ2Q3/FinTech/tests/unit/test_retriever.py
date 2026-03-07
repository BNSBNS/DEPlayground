"""Tests for the retriever."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from src.config import get_settings
from src.data.processors.chunker import Chunk
from src.rag.embedder import MockEmbedder
from src.rag.retriever import RetrievedChunk, Retriever
from src.rag.vector_store import VectorStore

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def embedder() -> MockEmbedder:
    return MockEmbedder(dimensions=128)


@pytest.fixture
def populated_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, embedder: MockEmbedder
) -> VectorStore:
    """VectorStore pre-populated with sample chunks."""
    monkeypatch.setenv("CHROMA_PERSIST_DIR", str(tmp_path))
    get_settings.cache_clear()

    store = VectorStore(collection_name="test_retriever", persist_dir=str(tmp_path))
    chunks = [
        Chunk(
            text="Apple Q4 revenue was $89.5 billion, up 6% year-over-year.",
            doc_name="AAPL_Q4_2024",
            section="cfo_remarks",
            chunk_index=0,
            token_count=15,
        ),
        Chunk(
            text="NVIDIA reported data center revenue of $18.4 billion.",
            doc_name="NVDA_Q3_2024",
            section="ceo_remarks",
            chunk_index=0,
            token_count=12,
        ),
        Chunk(
            text="The Fed held the federal funds rate at 5.25-5.50%.",
            doc_name="fed_minutes",
            section="summary",
            chunk_index=0,
            token_count=14,
        ),
    ]
    embeddings = embedder.embed_texts([c.text for c in chunks])
    store.add_chunks(chunks, embeddings)

    yield store
    get_settings.cache_clear()


class TestRetriever:
    def test_retrieve_returns_chunks(
        self, populated_store: VectorStore, embedder: MockEmbedder
    ) -> None:
        retriever = Retriever(populated_store, embedder)
        results = retriever.retrieve("Apple revenue")
        assert len(results) > 0
        assert all(isinstance(r, RetrievedChunk) for r in results)

    def test_retrieve_scores_are_bounded(
        self, populated_store: VectorStore, embedder: MockEmbedder
    ) -> None:
        retriever = Retriever(populated_store, embedder)
        results = retriever.retrieve("NVIDIA data center growth")
        for r in results:
            assert -1.0 <= r.score <= 1.0

    def test_retrieve_respects_n_results(
        self, populated_store: VectorStore, embedder: MockEmbedder
    ) -> None:
        retriever = Retriever(populated_store, embedder)
        results = retriever.retrieve("financial data", n_results=2)
        assert len(results) == 2

    def test_retrieve_metadata_preserved(
        self, populated_store: VectorStore, embedder: MockEmbedder
    ) -> None:
        retriever = Retriever(populated_store, embedder)
        results = retriever.retrieve("interest rates")
        assert all(r.doc_name for r in results)
        assert all(r.section for r in results)

    def test_empty_store_returns_empty(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, embedder: MockEmbedder
    ) -> None:
        monkeypatch.setenv("CHROMA_PERSIST_DIR", str(tmp_path / "empty"))
        get_settings.cache_clear()
        store = VectorStore(collection_name="empty_test", persist_dir=str(tmp_path / "empty"))
        retriever = Retriever(store, embedder)
        results = retriever.retrieve("anything")
        assert results == []
        get_settings.cache_clear()
