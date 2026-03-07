"""RAGAs-style evaluation for the query engine."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.evaluation.tracker import save_eval_result
from src.logging import get_logger
from src.models.evaluation import EvalResult, EvalSuite

if TYPE_CHECKING:
    import asyncpg

    from src.reasoning.engine import QueryEngine

logger = get_logger("evaluation.ragas")

GOLDEN_TEST_SET: list[dict[str, Any]] = [
    {
        "question": "What tables does the orders_mart dbt model depend on?",
        "expected_answer": "The orders_mart model depends on stg_orders and stg_customers.",
        "expected_sources": ["dbt_model:orders_mart", "dbt_model:stg_orders"],
    },
    {
        "question": "Who owns the customer_analytics schema?",
        "expected_answer": "The customer_analytics schema is owned by the analytics-team.",
        "expected_sources": ["owner:analytics-team", "schema:customer_analytics"],
    },
    {
        "question": "What columns does the users table have?",
        "expected_answer": "The users table has id, email, name, created_at, and status columns.",
        "expected_sources": ["table:users"],
    },
    {
        "question": "Which dashboards use the revenue_daily metric?",
        "expected_answer": "The Executive KPIs and Sales Overview dashboards use revenue_daily.",
        "expected_sources": ["metric:revenue_daily", "dashboard:executive_kpis"],
    },
    {
        "question": "What is the lineage of the revenue_daily metric?",
        "expected_answer": (
            "revenue_daily is derived from orders_mart which sources from "
            "stg_orders and stg_payments."
        ),
        "expected_sources": ["metric:revenue_daily", "dbt_model:orders_mart"],
    },
]


async def evaluate_query_engine(
    engine: QueryEngine,
    pool: asyncpg.Pool,  # type: ignore[type-arg]
) -> EvalSuite:
    """Run the golden test set through the engine and compute RAGAs metrics."""
    results: list[EvalResult] = []

    for test_case in GOLDEN_TEST_SET:
        question = test_case["question"]
        expected_answer = test_case["expected_answer"]
        expected_sources = set(test_case["expected_sources"])

        logger.info("evaluating_question", question=question)
        response = await engine.run(question)

        # Faithfulness: how grounded is the answer in retrieved sources?
        faithfulness = _compute_faithfulness(response.answer, response.sources)

        # Answer relevancy: how relevant is the answer to the question?
        answer_relevancy = _compute_answer_relevancy(
            question, response.answer, expected_answer
        )

        # Context precision/recall: compare retrieved vs expected sources
        retrieved_sources = {
            s.metadata.get("source_key", "") for s in response.sources
        }
        context_precision = _precision(retrieved_sources, expected_sources)
        context_recall = _recall(retrieved_sources, expected_sources)

        result = EvalResult(
            question=question,
            answer=response.answer,
            faithfulness=faithfulness,
            answer_relevancy=answer_relevancy,
            context_precision=context_precision,
            context_recall=context_recall,
        )
        results.append(result)
        await save_eval_result(pool, result)

    suite = EvalSuite(results=results)
    logger.info(
        "evaluation_suite_complete",
        mean_faithfulness=suite.mean_faithfulness,
        mean_relevancy=suite.mean_relevancy,
        mean_precision=suite.mean_precision,
        mean_recall=suite.mean_recall,
    )
    return suite


def _compute_faithfulness(
    answer: str,
    sources: list[Any],
) -> float:
    """Estimate faithfulness: proportion of answer sentences grounded in sources."""
    if not answer or not sources:
        return 0.0
    source_text = " ".join(s.content.lower() for s in sources)
    sentences = [s.strip() for s in answer.split(".") if s.strip()]
    if not sentences:
        return 0.0
    grounded = sum(
        1
        for sent in sentences
        if any(word in source_text for word in sent.lower().split() if len(word) > 3)
    )
    return min(grounded / len(sentences), 1.0)


def _compute_answer_relevancy(
    question: str,
    answer: str,
    expected: str,
) -> float:
    """Estimate relevancy via keyword overlap between answer and expected."""
    if not answer:
        return 0.0
    answer_words = set(answer.lower().split())
    expected_words = set(expected.lower().split())
    question_words = set(question.lower().split())
    relevant_words = expected_words | question_words
    if not relevant_words:
        return 0.0
    overlap = answer_words & relevant_words
    return min(len(overlap) / len(relevant_words), 1.0)


def _precision(retrieved: set[str], expected: set[str]) -> float:
    """Context precision: relevant retrieved / total retrieved."""
    if not retrieved:
        return 0.0
    relevant = retrieved & expected
    return len(relevant) / len(retrieved)


def _recall(retrieved: set[str], expected: set[str]) -> float:
    """Context recall: relevant retrieved / total expected."""
    if not expected:
        return 1.0
    relevant = retrieved & expected
    return len(relevant) / len(expected)
