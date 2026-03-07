"""RAG chain — retrieve context, build prompt, call Claude, parse response."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from src.rag.retriever import RetrievedChunk, Retriever


class Source(BaseModel):
    """A cited source from the RAG pipeline."""

    model_config = ConfigDict(extra="forbid")

    doc_name: str
    section: str
    score: float


class RAGResponse(BaseModel):
    """Response from the RAG chain with computed metrics."""

    model_config = ConfigDict(extra="forbid")

    answer: str
    sources: list[Source]
    retrieval_score: float  # avg relevance of top-k (from vector distance)
    source_agreement: float  # fraction of sources supporting the answer (0-1)


_SYSTEM_PROMPT = """\
You are a financial research analyst. Answer ONLY from the provided context.
- Cite sources as [doc_name - section_name]
- Never extrapolate figures or invent numbers
- Distinguish reported vs forward-looking statements
- Note the filing/transcript date for temporal context
- If context is insufficient, say "Insufficient information in available documents."
"""


def _build_context(chunks: list[RetrievedChunk]) -> str:
    """Format retrieved chunks as context for the LLM."""
    parts: list[str] = []
    for i, c in enumerate(chunks, 1):
        parts.append(f"[Source {i}: {c.doc_name} - {c.section}]\n{c.text}\n")
    return "\n".join(parts)


class RAGChain:
    """Retrieve relevant context, then synthesize an answer with Claude."""

    def __init__(self, retriever: Retriever) -> None:
        self.retriever = retriever

    def query(self, question: str, n_results: int = 5) -> RAGResponse:
        """Answer a question using RAG."""
        chunks = self.retriever.retrieve(question, n_results=n_results)

        if not chunks:
            return RAGResponse(
                answer="Insufficient information in available documents.",
                sources=[],
                retrieval_score=0.0,
                source_agreement=0.0,
            )

        context = _build_context(chunks)
        answer = self._call_llm(question, context)

        sources = [Source(doc_name=c.doc_name, section=c.section, score=c.score) for c in chunks]
        retrieval_score = sum(c.score for c in chunks) / len(chunks)
        # Source agreement: fraction of unique docs (more docs = broader support)
        unique_docs = len({c.doc_name for c in chunks})
        source_agreement = min(unique_docs / max(n_results, 1), 1.0)

        return RAGResponse(
            answer=answer,
            sources=sources,
            retrieval_score=retrieval_score,
            source_agreement=source_agreement,
        )

    def _call_llm(self, question: str, context: str) -> str:
        """Call Claude to synthesize an answer from context."""
        import anthropic  # noqa: PLC0415

        client = anthropic.Anthropic()
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Context:\n{context}\n\nQuestion: {question}\n\n"
                        "Answer based only on the context above."
                    ),
                }
            ],
        )
        return message.content[0].text
