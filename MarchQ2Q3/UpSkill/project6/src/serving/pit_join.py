from __future__ import annotations

from datetime import datetime


def build_pit_join_query(
    feature_names: list[str],
    entity_join_key: str,
    start_time: datetime,
    end_time: datetime,
    entity_table: str = "entity_df",
) -> str:
    """Build a point-in-time correct join SQL query.

    Uses SELECT DISTINCT ON to get the latest feature value
    at or before each entity's event_timestamp.
    """
    ctes: list[str] = []
    for fname in feature_names:
        cte = f"""
    {fname}_latest AS (
        SELECT DISTINCT ON (e.{entity_join_key})
            e.{entity_join_key},
            e.event_timestamp AS as_of,
            fv.value AS {fname},
            fv.event_timestamp AS {fname}_timestamp
        FROM {entity_table} e
        LEFT JOIN feature_values fv
            ON fv.feature_name = '{fname}'
            AND fv.entity_key = e.{entity_join_key}::text
            AND fv.event_timestamp <= e.event_timestamp
        WHERE e.event_timestamp BETWEEN '{start_time.isoformat()}'
            AND '{end_time.isoformat()}'
        ORDER BY e.{entity_join_key}, fv.event_timestamp DESC
    )"""
        ctes.append(cte)

    # Build final SELECT joining all CTEs
    select_cols = [f"e.{entity_join_key}", "e.event_timestamp"]
    join_clauses: list[str] = []
    for fname in feature_names:
        select_cols.append(f"{fname}_latest.{fname}")
        join_clauses.append(
            f"LEFT JOIN {fname}_latest "
            f"ON {fname}_latest.{entity_join_key} = e.{entity_join_key}"
        )

    query = f"""WITH{','.join(ctes)}
SELECT
    {', '.join(select_cols)}
FROM {entity_table} e
{chr(10).join(join_clauses)}
WHERE e.event_timestamp BETWEEN '{start_time.isoformat()}' AND '{end_time.isoformat()}'
ORDER BY e.{entity_join_key}, e.event_timestamp"""

    return query


def build_single_feature_pit_query(
    feature_name: str,
    entity_key: str,
    as_of: datetime,
) -> str:
    """Build a simple PIT query for a single feature and entity."""
    return f"""
SELECT DISTINCT ON (entity_key)
    entity_key,
    feature_name,
    value,
    event_timestamp
FROM feature_values
WHERE feature_name = '{feature_name}'
  AND entity_key = '{entity_key}'
  AND event_timestamp <= '{as_of.isoformat()}'
ORDER BY entity_key, event_timestamp DESC
LIMIT 1
"""
