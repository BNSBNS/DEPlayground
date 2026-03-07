"""Schema detector — diffs current columns against stored snapshot."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from src.logging import get_logger

if TYPE_CHECKING:
    import asyncpg
from src.models.metrics import DataQualityMetric, MetricStatus, MetricType

logger = get_logger(__name__)


async def check_schema(
    pool: asyncpg.Pool[asyncpg.Record],
    table: str,
) -> DataQualityMetric:
    """Check schema changes by diffing information_schema against stored snapshot.

    Additions → warning, removals/type changes → critical.
    Stores a new snapshot after each check.
    """
    parts = table.split(".")
    db_name = parts[0] if len(parts) > 2 else "default"
    schema_name = parts[1] if len(parts) > 2 else "public"
    table_name = parts[-1]

    try:
        # Get current schema from information_schema
        rows = await pool.fetch(
            """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = $1 AND table_name = $2
            ORDER BY ordinal_position
            """,
            schema_name,
            table_name,
        )
        current_cols = {
            row["column_name"]: {
                "data_type": row["data_type"],
                "nullable": row["is_nullable"],
            }
            for row in rows
        }
    except Exception as e:
        logger.warning("Schema check failed", table=table, error=str(e))
        return DataQualityMetric(
            table_name=table_name,
            database=db_name,
            schema_name=schema_name,
            metric_type=MetricType.SCHEMA,
            value=0.0,
            status=MetricStatus.UNKNOWN,
            metadata={"error": str(e)},
        )

    # Get previous snapshot
    snapshot_row = await pool.fetchrow(
        """
        SELECT columns FROM schema_snapshots
        WHERE table_name = $1 AND database = $2 AND schema_name = $3
        """,
        table_name,
        db_name,
        schema_name,
    )

    if snapshot_row is None:
        # First check — store snapshot, return healthy
        await pool.execute(
            """
            INSERT INTO schema_snapshots (table_name, database, schema_name, columns)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (table_name, database, schema_name)
            DO UPDATE SET columns = $4, captured_at = NOW()
            """,
            table_name,
            db_name,
            schema_name,
            json.dumps(current_cols),
        )
        return DataQualityMetric(
            table_name=table_name,
            database=db_name,
            schema_name=schema_name,
            metric_type=MetricType.SCHEMA,
            value=0.0,
            status=MetricStatus.HEALTHY,
            metadata={"note": "initial snapshot stored", "column_count": len(current_cols)},
        )

    previous_cols: dict[str, dict[str, str]] = json.loads(snapshot_row["columns"])

    # Diff
    added = set(current_cols.keys()) - set(previous_cols.keys())
    removed = set(previous_cols.keys()) - set(current_cols.keys())
    type_changed = {
        col
        for col in set(current_cols.keys()) & set(previous_cols.keys())
        if current_cols[col]["data_type"] != previous_cols[col]["data_type"]
    }

    changes = len(added) + len(removed) + len(type_changed)

    if removed or type_changed:
        status = MetricStatus.CRITICAL
    elif added:
        status = MetricStatus.WARNING
    else:
        status = MetricStatus.HEALTHY

    # Update snapshot
    await pool.execute(
        """
        UPDATE schema_snapshots SET columns = $1, captured_at = NOW()
        WHERE table_name = $2 AND database = $3 AND schema_name = $4
        """,
        json.dumps(current_cols),
        table_name,
        db_name,
        schema_name,
    )

    return DataQualityMetric(
        table_name=table_name,
        database=db_name,
        schema_name=schema_name,
        metric_type=MetricType.SCHEMA,
        value=float(changes),
        status=status,
        metadata={
            "added": list(added),
            "removed": list(removed),
            "type_changed": list(type_changed),
        },
    )
