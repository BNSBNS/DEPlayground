from __future__ import annotations

import structlog

from src.models.events import PipelineFailureEvent

log = structlog.get_logger(__name__)


async def gather_context(
    event: PipelineFailureEvent,
    pool: object | None = None,
) -> dict[str, str]:
    """Gather contextual information for diagnosis.

    In production, queries the DB for error history, schema info, etc.
    In simulation mode, returns synthetic context.
    """
    context: dict[str, str] = {
        "pipeline": event.pipeline_name,
        "task": event.task_name,
        "affected_table": event.affected_table,
        "affected_column": event.affected_column,
        "schema": event.schema_name,
        "error_type": event.error_type,
    }

    if pool is not None:
        try:
            async with pool.acquire() as conn:  # type: ignore[union-attr]
                rows = await conn.fetch(
                    """
                    SELECT error_message, created_at
                    FROM pipeline_events
                    WHERE affected_table = $1
                    ORDER BY created_at DESC
                    LIMIT 5
                    """,
                    event.affected_table,
                )
                history = [
                    f"[{r['created_at']}] {r['error_message']}" for r in rows
                ]
                context["error_history"] = "\n".join(history) if history else "none"
        except Exception:
            await log.awarning("context_db_query_failed", table=event.affected_table)
            context["error_history"] = "unavailable"
    else:
        context["error_history"] = "simulation_mode"

    return context
