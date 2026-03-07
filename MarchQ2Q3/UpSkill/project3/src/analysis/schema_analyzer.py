from __future__ import annotations

import structlog

log = structlog.get_logger(__name__)


def compare_schemas(
    current_columns: list[dict[str, str]],
    expected_columns: list[dict[str, str]],
) -> str:
    """Compare current vs expected schema and return a diff summary."""
    current_names = {c["name"] for c in current_columns}
    expected_names = {c["name"] for c in expected_columns}

    added = current_names - expected_names
    removed = expected_names - current_names
    common = current_names & expected_names

    diffs: list[str] = []

    for col in sorted(added):
        diffs.append(f"+ {col} (new column in source)")

    for col in sorted(removed):
        diffs.append(f"- {col} (missing from source)")

    current_types = {c["name"]: c.get("type", "") for c in current_columns}
    expected_types = {c["name"]: c.get("type", "") for c in expected_columns}

    for col in sorted(common):
        if current_types.get(col) != expected_types.get(col):
            diffs.append(
                f"~ {col}: {expected_types.get(col, '?')} -> {current_types.get(col, '?')}"
            )

    if not diffs:
        return "no schema differences detected"

    return "\n".join(diffs)


async def get_table_schema(
    pool: object | None,
    table_name: str,
    schema_name: str = "public",
) -> list[dict[str, str]]:
    """Fetch column info from information_schema. Returns empty list in simulation."""
    if pool is None:
        return []

    try:
        async with pool.acquire() as conn:  # type: ignore[union-attr]
            rows = await conn.fetch(
                """
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = $1 AND table_name = $2
                ORDER BY ordinal_position
                """,
                schema_name,
                table_name,
            )
            return [{"name": r["column_name"], "type": r["data_type"]} for r in rows]
    except Exception:
        await log.awarning("schema_fetch_failed", table=table_name)
        return []
