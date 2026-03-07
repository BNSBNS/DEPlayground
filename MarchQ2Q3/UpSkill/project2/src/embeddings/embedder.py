"""Embedding wrapper using sentence-transformers (all-MiniLM-L6-v2, 384-dim)."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

_MODEL_NAME = "all-MiniLM-L6-v2"
_EMBEDDING_DIM = 384


class Embedder:
    """Lazy-loading embedding wrapper around sentence-transformers."""

    def __init__(self, model_name: str = _MODEL_NAME) -> None:
        self._model_name = model_name
        self._model: SentenceTransformer | None = None

    def _load_model(self) -> SentenceTransformer:
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self._model_name)
        return self._model

    async def embed(self, text: str) -> list[float]:
        """Embed a single text string, returning a 384-dim vector."""
        model = self._load_model()
        vec = await asyncio.to_thread(model.encode, text)
        return vec.tolist()

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts, returning a list of 384-dim vectors."""
        if not texts:
            return []
        model = self._load_model()
        vecs = await asyncio.to_thread(model.encode, texts)
        return [v.tolist() for v in vecs]


_embedder: Embedder | None = None


def get_embedder() -> Embedder:
    """Return a module-level singleton Embedder instance."""
    global _embedder  # noqa: PLW0603
    if _embedder is None:
        _embedder = Embedder()
    return _embedder
