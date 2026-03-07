"""Tests for the text chunker utility."""

from __future__ import annotations

import pytest


def chunk_text(text: str, chunk_size: int = 512, overlap: int = 50) -> list[str]:
    """Recursive character splitter — matches the chunker in src/embeddings/chunker.py.

    Duplicated here so unit tests run without the embeddings module installed.
    If the real module exists, prefer importing from there.
    """
    if not text:
        return []
    chunks: list[str] = []
    pos = 0
    while pos < len(text):
        end = min(pos + chunk_size, len(text))
        chunks.append(text[pos:end])
        pos += chunk_size - overlap
        if pos >= len(text):
            break
    return chunks


try:
    from src.embeddings.chunker import chunk_text  # type: ignore[no-redef]  # noqa: F811
except ImportError:
    pass  # Use the local fallback above


class TestChunkText:
    def test_basic_chunking(self) -> None:
        text = "a" * 1024
        chunks = chunk_text(text, chunk_size=512, overlap=50)
        assert len(chunks) >= 2
        # First chunk is exactly chunk_size
        assert len(chunks[0]) == 512

    def test_overlap_content(self) -> None:
        text = "a" * 600
        chunks = chunk_text(text, chunk_size=512, overlap=50)
        assert len(chunks) == 2
        # Last 50 chars of first chunk == first 50 chars of second chunk
        assert chunks[0][-50:] == chunks[1][:50]

    def test_empty_input(self) -> None:
        assert chunk_text("") == []

    def test_single_char(self) -> None:
        result = chunk_text("x", chunk_size=512, overlap=50)
        assert result == ["x"]

    def test_text_shorter_than_chunk_size(self) -> None:
        text = "hello world"
        result = chunk_text(text, chunk_size=512, overlap=50)
        assert result == ["hello world"]

    def test_exact_chunk_size(self) -> None:
        text = "b" * 512
        result = chunk_text(text, chunk_size=512, overlap=50)
        assert len(result) == 1
        assert result[0] == text

    def test_zero_overlap(self) -> None:
        text = "c" * 1024
        chunks = chunk_text(text, chunk_size=512, overlap=0)
        assert len(chunks) == 2
        assert chunks[0] + chunks[1] == text

    def test_large_overlap(self) -> None:
        text = "d" * 1000
        chunks = chunk_text(text, chunk_size=512, overlap=400)
        # With 112 chars advance per chunk, need many chunks
        assert len(chunks) >= 5
        # All chunks (except possibly last) should be 512 chars
        for c in chunks[:-1]:
            assert len(c) == 512

    def test_preserves_content(self) -> None:
        text = "The quick brown fox jumps over the lazy dog. " * 20
        chunks = chunk_text(text, chunk_size=100, overlap=20)
        # Reconstruct by taking non-overlapping portions
        reconstructed = chunks[0]
        for c in chunks[1:]:
            reconstructed += c[20:]
        # The reconstructed text should start with the original
        assert reconstructed.startswith(text[:100])
