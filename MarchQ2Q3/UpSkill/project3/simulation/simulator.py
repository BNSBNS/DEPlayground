"""Simulate realistic pipeline failure events at regular intervals."""

import asyncio
import random
from datetime import datetime
from uuid import uuid4

import structlog

from src.models.events import (
    ErrorType,
    EventSeverity,
    EventSource,
    PipelineFailureEvent,
)

log = structlog.get_logger(__name__)

# Weighted distribution: 40% schema, 25% null, 15% type, 10% timeout, 10% misc
ERROR_TEMPLATES: list[tuple[float, dict]] = [
    (0.40, {
        "error_type": ErrorType.SCHEMA_MISMATCH,
        "messages": [
            "column '{col}' not found in source table '{table}'",
            "relation '{schema}.{table}' does not exist",
            "missing column '{col}' after upstream migration",
            "schema mismatch: unexpected columns in '{table}'",
        ],
    }),
    (0.25, {
        "error_type": ErrorType.NULL_VIOLATION,
        "messages": [
            "null value in column '{col}' violates not-null constraint",
            "NOT NULL constraint failed: {table}.{col}",
            "column '{col}' cannot be null",
        ],
    }),
    (0.15, {
        "error_type": ErrorType.TYPE_MISMATCH,
        "messages": [
            "invalid input syntax for type integer: '{col}'",
            "cannot cast '{col}' value to numeric",
            "type mismatch in column '{col}' of '{table}'",
        ],
    }),
    (0.10, {
        "error_type": ErrorType.TIMEOUT,
        "messages": [
            "connection timed out after 30s",
            "deadline exceeded: query on '{table}' took too long",
            "connection refused to database host",
        ],
    }),
    (0.10, {
        "error_type": ErrorType.VOLUME_ANOMALY,
        "messages": [
            "unexpected row count in '{table}': expected ~10000, got 0",
            "volume anomaly detected in '{table}'",
        ],
    }),
]

TABLES = ["orders", "customers", "payments", "products", "shipments"]
COLUMNS = ["id", "amount", "status", "email", "discount", "tax_rate", "created_at"]
PIPELINES = ["daily_orders", "customer_sync", "payment_pipeline", "product_catalog"]
TASKS = ["extract", "transform", "load", "validate", "publish"]


def _pick_error() -> tuple[ErrorType, str]:
    """Pick an error type based on weighted distribution."""
    r = random.random()
    cumulative = 0.0
    for weight, template in ERROR_TEMPLATES:
        cumulative += weight
        if r <= cumulative:
            table = random.choice(TABLES)
            col = random.choice(COLUMNS)
            msg = random.choice(template["messages"]).format(
                table=table, col=col, schema="public"
            )
            return template["error_type"], msg
    # Fallback
    return ErrorType.UNKNOWN, "unknown pipeline error"


def generate_event() -> PipelineFailureEvent:
    """Generate a single realistic failure event."""
    error_type, message = _pick_error()
    table = random.choice(TABLES)
    col = random.choice(COLUMNS)

    return PipelineFailureEvent(
        event_id=uuid4(),
        source=random.choice(list(EventSource)),
        severity=random.choice(list(EventSeverity)),
        pipeline_name=random.choice(PIPELINES),
        task_name=random.choice(TASKS),
        error_message=message,
        error_type=error_type,
        affected_table=table,
        affected_column=col,
        timestamp=datetime.utcnow(),
        log_snippet=f"ERROR at {datetime.utcnow().isoformat()}: {message}\nTraceback...",
    )


async def run_simulator(interval_min: float = 1.0, interval_max: float = 2.0) -> None:
    """Continuously generate failure events at random intervals."""
    await log.ainfo("simulator_started", interval=f"{interval_min}-{interval_max}min")

    while True:
        event = generate_event()
        await log.ainfo(
            "simulated_event",
            event_id=str(event.event_id),
            pipeline=event.pipeline_name,
            error_type=event.error_type,
            table=event.affected_table,
        )

        delay = random.uniform(interval_min * 60, interval_max * 60)
        await asyncio.sleep(delay)


if __name__ == "__main__":
    asyncio.run(run_simulator())
