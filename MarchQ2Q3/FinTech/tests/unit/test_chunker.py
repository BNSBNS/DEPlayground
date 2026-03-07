"""Tests for the document chunker."""

from __future__ import annotations

from src.data.processors.chunker import Chunk, chunk_document


class TestChunkDocument:
    def test_simple_text_produces_chunks(self) -> None:
        text = "This is sentence one. This is sentence two. This is sentence three."
        chunks = chunk_document(text, "test_doc")
        assert len(chunks) >= 1
        assert all(isinstance(c, Chunk) for c in chunks)

    def test_chunk_metadata(self) -> None:
        text = "Hello world. This is a test document."
        chunks = chunk_document(text, "mydoc", metadata={"ticker": "AAPL"})
        assert chunks[0].doc_name == "mydoc"
        assert chunks[0].metadata["ticker"] == "AAPL"

    def test_token_count_populated(self) -> None:
        text = "The quick brown fox jumps over the lazy dog. " * 10
        chunks = chunk_document(text, "test")
        assert all(c.token_count > 0 for c in chunks)

    def test_respects_max_tokens(self) -> None:
        # Long text that should split into multiple chunks
        text = "This is a fairly long sentence that contains many words. " * 200
        chunks = chunk_document(text, "long_doc", max_tokens=128, overlap_tokens=20)
        assert len(chunks) > 1
        # Each chunk should be near the token limit
        for c in chunks[:-1]:  # last chunk may be shorter
            assert c.token_count <= 200  # some slack for sentence boundaries

    def test_section_splitting(self) -> None:
        text = (
            "Opening remarks about the company.\n\n"
            "CEO Remarks Prepared\n"
            "The CEO discussed growth strategy. Revenue grew 15%.\n\n"
            "CFO Remarks Prepared\n"
            "The CFO reviewed financials. Margins expanded 200bps.\n\n"
            "Question and Answer Session\n"
            "Analyst asked about guidance. Management provided outlook."
        )
        chunks = chunk_document(text, "transcript")
        sections = {c.section for c in chunks}
        # Should have found at least the introduction and one named section
        assert len(sections) >= 2

    def test_chunk_index_sequential(self) -> None:
        text = "Sentence one. " * 100
        chunks = chunk_document(text, "test", max_tokens=64)
        for i, c in enumerate(chunks):
            assert c.chunk_index == i

    def test_empty_text_returns_chunk(self) -> None:
        chunks = chunk_document("", "empty_doc")
        # Should handle gracefully (empty or single chunk)
        assert isinstance(chunks, list)

    def test_no_mid_sentence_split(self) -> None:
        text = "First sentence here. Second sentence here. Third sentence here."
        chunks = chunk_document(text, "test", max_tokens=16, overlap_tokens=0)
        for c in chunks:
            # Each chunk should end with a complete sentence (period)
            stripped = c.text.strip()
            if stripped:
                assert stripped[-1] in ".!?", f"Chunk ends mid-sentence: {stripped[-20:]}"
