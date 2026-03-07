"""Persistence layer for evaluation results."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.logging import get_logger
from src.models.evaluation import EvalResult

if TYPE_CHECKING:
    import asyncpg

logger = get_logger("evaluation.tracker")


async def save_eval_result(
    pool: asyncpg.Pool,  # type: ignore[type-arg]
    result: EvalResult,
) -> None:
    """Insert a single evaluation result into the eval_results table."""
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO eval_results
                (question, answer, faithfulness, answer_relevancy,
                 context_precision, context_recall, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            result.question,
            result.answer,
            result.faithfulness,
            result.answer_relevancy,
            result.context_precision,
            result.context_recall,
            result.created_at,
        )
    logger.debug("eval_result_saved", question=result.question[:60])


async def get_eval_history(
    pool: asyncpg.Pool,  # type: ignore[type-arg]
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Retrieve recent evaluation results, newest first."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, question, answer, faithfulness, answer_relevancy,
                   context_precision, context_recall, created_at
            FROM eval_results
            ORDER BY created_at DESC
            LIMIT $1
            """,
            limit,
        )
    return [dict(row) for row in rows]
