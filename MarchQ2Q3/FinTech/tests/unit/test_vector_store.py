"""Tests for embedder and vector store."""

from __future__ import annotations

import pytest

from src.config import get_settings
from src.data.processors.chunker import Chunk
from src.rag.embedder import MockEmbedder
from src.rag.vector_store import VectorStore


@pytest.fixture
def embedder() -> MockEmbedder:
    return MockEmbedder(dimensions=128)


@pytest.fixture
def vector_store(tmp_path: str, monkeypatch: pytest.MonkeyPatch) -> VectorStore:
    """VectorStore backed by a temp directory."""
    monkeypatch.setenv("CHROMA_PERSIST_DIR", str(tmp_path))
    get_settings.cache_clear()
    vs = VectorStore(collection_name="test_collection", persist_dir=str(tmp_path))
    yield vs
    get_settings.cache_clear()


@pytest.fixture
def sample_chunks() -> list[Chunk]:
    return [
        Chunk(
            text="Apple reported strong Q4 earnings with revenue of $89.5 billion.",
            doc_name="AAPL_Q4_2024",
            section="introduction",
            chunk_index=0,
            token_count=15,
            metadata={"ticker": "AAPL"},
        ),
        Chunk(
            text="NVIDIA's data center revenue grew 400% year-over-year.",
            doc_name="NVDA_Q3_2024",
            section="ceo_remarks",
            chunk_index=0,
            token_count=12,
            metadata={"ticker": "NVDA"},
        ),
        Chunk(
            text="The Federal Reserve held rates steady at 5.25-5.50%.",
            doc_name="fed_minutes_2024",
            section="summary",
            chunk_index=0,
            token_count=13,
            metadata={"source": "fed"},
        ),
    ]


class TestMockEmbedder:
    def test_deterministic(self, embedder: MockEmbedder) -> None:
        v1 = embedder.embed_query("hello world")
        v2 = embedder.embed_query("hello world")
        assert v1 == v2

    def test_different_inputs_differ(self, embedder: MockEmbedder) -> None:
        v1 = embedder.embed_query("apple earnings")
        v2 = embedder.embed_query("nvidia revenue")
        assert v1 != v2

    def test_correct_dimensions(self, embedder: MockEmbedder) -> None:
        v = embedder.embed_query("test")
        assert len(v) == 128

    def test_unit_norm(self, embedder: MockEmbedder) -> None:
        v = embedder.embed_query("test text")
        norm = sum(x * x for x in v) ** 0.5
        assert abs(norm - 1.0) < 1e-6

    def test_batch_embed(self, embedder: MockEmbedder) -> None:
        texts = ["text one", "text two", "text three"]
        vecs = embedder.embed_texts(texts)
        assert len(vecs) == 3
        assert all(len(v) == 128 for v in vecs)


class TestVectorStore:
    def test_add_and_count(
        self,
        vector_store: VectorStore,
        sample_chunks: list[Chunk],
        embedder: MockEmbedder,
    ) -> None:
        embeddings = embedder.embed_texts([c.text for c in sample_chunks])
        vector_store.add_chunks(sample_chunks, embeddings)
        assert vector_store.count == 3

    def test_query_returns_results(
        self,
        vector_store: VectorStore,
        sample_chunks: list[Chunk],
        embedder: MockEmbedder,
    ) -> None:
        embeddings = embedder.embed_texts([c.text for c in sample_chunks])
        vector_store.add_chunks(sample_chunks, embeddings)

        query_vec = embedder.embed_query("Apple earnings report")
        results = vector_store.query(query_vec, n_results=2)
        assert len(results["documents"][0]) == 2

    def test_query_metadata_preserved(
        self,
        vector_store: VectorStore,
        sample_chunks: list[Chunk],
        embedder: MockEmbedder,
    ) -> None:
        embeddings = embedder.embed_texts([c.text for c in sample_chunks])
        vector_store.add_chunks(sample_chunks, embeddings)

        query_vec = embedder.embed_query("NVIDIA data center")
        results = vector_store.query(query_vec, n_results=1)
        meta = results["metadatas"][0][0]
        assert "doc_name" in meta
        assert "section" in meta

    def test_upsert_idempotent(
        self,
        vector_store: VectorStore,
        sample_chunks: list[Chunk],
        embedder: MockEmbedder,
    ) -> None:
        embeddings = embedder.embed_texts([c.text for c in sample_chunks])
        vector_store.add_chunks(sample_chunks, embeddings)
        vector_store.add_chunks(sample_chunks, embeddings)
        assert vector_store.count == 3  # no duplicates

    def test_reset(
        self,
        vector_store: VectorStore,
        sample_chunks: list[Chunk],
        embedder: MockEmbedder,
    ) -> None:
        embeddings = embedder.embed_texts([c.text for c in sample_chunks])
        vector_store.add_chunks(sample_chunks, embeddings)
        assert vector_store.count == 3
        vector_store.reset()
        assert vector_store.count == 0
