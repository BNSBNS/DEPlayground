"""Embedding utilities — OpenAI text-embedding-3-large + mock for testing."""

from __future__ import annotations

import hashlib
import struct


class Embedder:
    """Embed texts using OpenAI text-embedding-3-large."""

    def __init__(
        self,
        model: str = "text-embedding-3-large",
        dimensions: int = 1536,
    ) -> None:
        from openai import OpenAI  # noqa: PLC0415

        self.client = OpenAI()
        self.model = model
        self.dimensions = dimensions

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts. Batches in groups of 100."""
        all_embeddings: list[list[float]] = []
        for i in range(0, len(texts), 100):
            batch = texts[i : i + 100]
            response = self.client.embeddings.create(
                input=batch,
                model=self.model,
                dimensions=self.dimensions,
            )
            all_embeddings.extend([item.embedding for item in response.data])
        return all_embeddings

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query string."""
        return self.embed_texts([text])[0]


class MockEmbedder:
    """Deterministic hash-based embedder for testing (no API calls)."""

    def __init__(self, dimensions: int = 1536) -> None:
        self.dimensions = dimensions

    def _hash_to_vector(self, text: str) -> list[float]:
        """Convert text to a deterministic float vector via SHA-256."""
        h = hashlib.sha256(text.encode()).digest()
        # Repeat hash bytes to fill the needed dimensions (4 bytes per float)
        needed_bytes = self.dimensions * 4
        repeated = h * (needed_bytes // len(h) + 1)
        floats = list(struct.unpack(f"<{self.dimensions}f", repeated[:needed_bytes]))
        # Normalize to unit vector
        norm = sum(x * x for x in floats) ** 0.5
        if norm > 0:
            floats = [x / norm for x in floats]
        return floats

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed texts deterministically."""
        return [self._hash_to_vector(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query string."""
        return self._hash_to_vector(text)
