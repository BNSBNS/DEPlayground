"""RAG evaluation harness — measures retrieval and answer quality."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from src.logging import get_logger
from src.rag.chain import RAGChain
from src.rag.embedder import MockEmbedder
from src.rag.retriever import Retriever
from src.rag.vector_store import VectorStore

logger = get_logger(__name__)


@dataclass
class EvalResult:
    """Result for a single evaluation question."""

    question: str
    expected_keywords: list[str]
    answer: str
    retrieval_score: float
    keyword_hits: int
    keyword_total: int


@dataclass
class EvalSummary:
    """Summary metrics across all evaluation questions."""

    total_questions: int
    avg_retrieval_score: float
    avg_keyword_precision: float
    results: list[EvalResult]


def load_eval_set(path: str | Path) -> list[dict]:
    """Load evaluation Q&A pairs from JSON."""
    p = Path(path)
    if not p.exists():
        logger.warning("eval_set_not_found", path=str(p))
        return []
    with p.open() as f:
        return json.load(f)


def run_evaluation(
    eval_path: str | Path = "data/mock/eval/rag_eval.json",
    use_mock: bool = True,
) -> EvalSummary:
    """Run RAG evaluation against a Q&A set."""
    eval_set = load_eval_set(eval_path)
    if not eval_set:
        return EvalSummary(
            total_questions=0,
            avg_retrieval_score=0.0,
            avg_keyword_precision=0.0,
            results=[],
        )

    embedder = MockEmbedder()
    store = VectorStore()
    retriever = Retriever(store, embedder)
    chain = RAGChain(retriever) if not use_mock else None

    results: list[EvalResult] = []
    for item in eval_set:
        question = item["question"]
        expected = item.get("keywords", [])

        if chain:
            response = chain.query(question)
            answer = response.answer
            retrieval_score = response.retrieval_score
        else:
            # Mock mode: just test retrieval
            chunks = retriever.retrieve(question, n_results=5)
            answer = " ".join(c.text for c in chunks)
            retrieval_score = sum(c.score for c in chunks) / len(chunks) if chunks else 0.0

        hits = sum(1 for kw in expected if kw.lower() in answer.lower())
        results.append(
            EvalResult(
                question=question,
                expected_keywords=expected,
                answer=answer[:200],
                retrieval_score=retrieval_score,
                keyword_hits=hits,
                keyword_total=len(expected),
            )
        )

    avg_ret = sum(r.retrieval_score for r in results) / len(results)
    avg_kw = sum(r.keyword_hits / max(r.keyword_total, 1) for r in results) / len(results)

    summary = EvalSummary(
        total_questions=len(results),
        avg_retrieval_score=avg_ret,
        avg_keyword_precision=avg_kw,
        results=results,
    )

    logger.info(
        "eval_complete",
        questions=summary.total_questions,
        avg_retrieval=f"{summary.avg_retrieval_score:.3f}",
        avg_keyword_precision=f"{summary.avg_keyword_precision:.3f}",
    )
    return summary


if __name__ == "__main__":
    from src.logging import configure_logging

    configure_logging()
    summary = run_evaluation(use_mock=True)
    print(f"Questions: {summary.total_questions}")
    print(f"Avg retrieval score: {summary.avg_retrieval_score:.3f}")
    print(f"Avg keyword precision: {summary.avg_keyword_precision:.3f}")
