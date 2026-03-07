"""Evaluation suite endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from src.logging import get_logger
from src.models.evaluation import EvalSuite

router = APIRouter(prefix="/eval", tags=["evaluation"])
logger = get_logger("api.evaluation")


@router.post("/run", response_model=EvalSuite)
async def run_evaluation() -> EvalSuite:
    """Run the RAGAs evaluation suite against the query engine."""
    try:
        from src.db.pool import get_pool
        from src.evaluation.ragas import evaluate_query_engine
        from src.reasoning.engine import get_query_engine

        engine = get_query_engine()
        pool = get_pool()
        suite = await evaluate_query_engine(engine, pool)
        logger.info(
            "evaluation_completed",
            n_questions=len(suite.results),
            mean_faithfulness=suite.mean_faithfulness,
            mean_relevancy=suite.mean_relevancy,
        )
        return suite
    except ImportError as exc:
        raise HTTPException(
            status_code=501,
            detail=f"Evaluation dependencies not available: {exc}",
        )
    except Exception as exc:
        logger.error("evaluation_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {exc}")


@router.get("/results")
async def get_results(
    limit: int = Query(default=20, ge=1, le=100),
) -> list[dict[str, Any]]:
    """Return evaluation history, most recent first."""
    try:
        from src.db.pool import get_pool
        from src.evaluation.tracker import get_eval_history

        pool = get_pool()
        return await get_eval_history(pool, limit=limit)
    except ImportError as exc:
        raise HTTPException(
            status_code=501,
            detail=f"Evaluation tracker not available: {exc}",
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
