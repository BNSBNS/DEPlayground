"""Query engine: intent classification, hybrid retrieval, LLM-powered answer generation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.llm.factory import get_llm_provider
from src.logging import get_logger
from src.models.retrieval import QueryIntent, QueryResponse, RetrievalResult
from src.retrieval.hybrid import hybrid_search
from src.retrieval.reranker import rerank

if TYPE_CHECKING:
    import asyncpg

    from src.ingestion.store import IngestionStore

logger = get_logger("reasoning.engine")

_SYSTEM_PROMPT = (
    "You are a data governance assistant. Follow these rules strictly:\n"
    "1. Answer ONLY from the provided context. Never speculate.\n"
    "2. Cite sources using [Source N] notation.\n"
    "3. For lineage questions, describe the data flow step-by-step.\n"
    "4. If sources conflict, note the discrepancy explicitly.\n"
    "5. If the context is insufficient, say so clearly.\n"
)

_CLASSIFY_PROMPT = (
    "Classify this question into exactly one category.\n"
    "Categories: lineage, metadata, definition, change, general\n\n"
    "- lineage: questions about data flow, upstream/downstream dependencies\n"
    "- metadata: questions about table/column properties, ownership, stats\n"
    "- definition: questions about what a term, metric, or table means\n"
    "- change: questions about recent changes, modifications, history\n"
    "- general: anything else\n\n"
    "Question: {question}\n\n"
    "Reply with ONLY the category name, nothing else."
)

_ANSWER_PROMPT = (
    "{system}\n\n"
    "Context:\n{context}\n\n"
    "Question: {question}\n\n"
    "Provide a clear, concise answer citing sources with [Source N]."
)


class QueryEngine:
    """Orchestrates retrieval, reranking, and LLM answer generation."""

    def __init__(
        self,
        pool: asyncpg.Pool,  # type: ignore[type-arg]
        store: IngestionStore,
    ) -> None:
        self._pool = pool
        self._store = store

    async def run(self, question: str) -> QueryResponse:
        """Full query pipeline: classify -> retrieve -> rerank -> generate."""
        intent = await self._classify_intent(question)
        logger.info("query_classified", question=question[:80], intent=intent)

        # Retrieve
        results = await hybrid_search(
            self._pool, self._store, question, top_k=10
        )

        # Rerank
        results = await rerank(results, question, top_k=5)

        # Generate answer
        answer, confidence = await self._generate_answer(question, results)

        return QueryResponse(
            answer=answer,
            confidence=min(confidence, 0.95),
            sources=results,
            reasoning_path=f"intent={intent} -> hybrid_search -> rerank -> generate",
        )

    async def _classify_intent(self, question: str) -> QueryIntent:
        """Use LLM to classify the question intent."""
        llm = get_llm_provider()
        prompt = _CLASSIFY_PROMPT.format(question=question)

        try:
            response = await llm.complete([{"role": "user", "content": prompt}])
            category = response.content.strip().lower()

            try:
                return QueryIntent(category)
            except ValueError:
                logger.warning("unknown_intent", raw=category)
                return QueryIntent.general

        except Exception:
            logger.exception("classify_intent_failed")
            return QueryIntent.general

    async def _generate_answer(
        self,
        question: str,
        context: list[RetrievalResult],
    ) -> tuple[str, float]:
        """Generate an answer from context and estimate confidence."""
        if not context:
            return "I don't have enough context to answer this question.", 0.1

        # Assemble numbered context
        context_text = "\n".join(
            f"[Source {i + 1}] ({r.source}): {r.content}"
            for i, r in enumerate(context)
        )

        prompt = _ANSWER_PROMPT.format(
            system=_SYSTEM_PROMPT,
            context=context_text,
            question=question,
        )

        llm = get_llm_provider()
        response = await llm.complete([{"role": "user", "content": prompt}])

        confidence = self._estimate_confidence(context)

        logger.info(
            "answer_generated",
            question=question[:80],
            confidence=confidence,
            sources=len(context),
        )
        return response.content, confidence

    @staticmethod
    def _estimate_confidence(context: list[RetrievalResult]) -> float:
        """Estimate confidence based on source diversity and scores."""
        if not context:
            return 0.1

        sources = {r.source for r in context}
        avg_score = sum(r.score for r in context) / len(context)

        # Higher confidence when both vector and graph sources agree
        if sources == {"vector", "graph"}:
            base = 0.7
        elif len(sources) == 1:
            base = 0.5
        else:
            base = 0.3

        # Boost based on average retrieval score (capped contribution)
        confidence = base + min(avg_score * 0.25, 0.2)
        return min(confidence, 0.95)


_engine: QueryEngine | None = None


def set_query_engine(engine: QueryEngine) -> None:
    """Set the module-level singleton engine. Call once at application startup."""
    global _engine  # noqa: PLW0603
    _engine = engine


def get_query_engine() -> QueryEngine:
    """Return the singleton query engine. Raises RuntimeError if not initialized."""
    if _engine is None:
        raise RuntimeError("QueryEngine not initialized — call set_query_engine() at startup")
    return _engine
