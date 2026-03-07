from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from src.ingestion.store import store

if TYPE_CHECKING:
    import asyncpg

log = structlog.get_logger(__name__)


async def ingest_schemas(pool: asyncpg.Pool[asyncpg.Record]) -> dict[str, Any]:
    """Read database metadata from information_schema and build graph nodes.

    Creates a Database -> Schema -> Table -> Column hierarchy with BELONGS_TO
    edges and approximate row counts from pg_class.reltuples.
    """
    counts = {"databases": 0, "schemas": 0, "tables": 0, "columns": 0}

    async with pool.acquire() as conn:
        db_name = await conn.fetchval("SELECT current_database()")
        db_id = f"db:{db_name}"
        store.add_node(db_id, "Database", db_name)
        counts["databases"] = 1
        log.info("ingesting_database", database=db_name)

        # -- Schemas -------------------------------------------------------
        schemas = await conn.fetch(
            "SELECT schema_name FROM information_schema.schemata "
            "WHERE schema_name NOT IN ('pg_catalog', 'information_schema', 'pg_toast')"
        )
        for row in schemas:
            schema_name: str = row["schema_name"]
            schema_id = f"schema:{db_name}.{schema_name}"
            store.add_node(schema_id, "Schema", schema_name, database=db_name)
            store.add_edge(schema_id, db_id, "BELONGS_TO")
            counts["schemas"] += 1

        # -- Tables --------------------------------------------------------
        tables = await conn.fetch(
            "SELECT table_schema, table_name, table_type "
            "FROM information_schema.tables "
            "WHERE table_schema NOT IN "
            "('pg_catalog', 'information_schema', 'pg_toast')"
        )
        for row in tables:
            schema_name = row["table_schema"]
            table_name: str = row["table_name"]
            fqn = f"{db_name}.{schema_name}.{table_name}"
            table_id = f"table:{fqn}"

            store.add_node(
                table_id,
                "Table",
                table_name,
                schema=schema_name,
                database=db_name,
                table_type=row["table_type"],
            )
            store.add_edge(table_id, f"schema:{db_name}.{schema_name}", "BELONGS_TO")
            counts["tables"] += 1

        # -- Approximate row counts ----------------------------------------
        row_counts = await conn.fetch(
            "SELECT n.nspname AS schema_name, c.relname AS table_name, "
            "       c.reltuples::bigint AS approx_rows "
            "FROM pg_class c "
            "JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE c.relkind IN ('r', 'p') "
            "  AND n.nspname NOT IN "
            "  ('pg_catalog', 'information_schema', 'pg_toast')"
        )
        row_count_map: dict[str, int] = {
            f"{r['schema_name']}.{r['table_name']}": int(r["approx_rows"])
            for r in row_counts
        }
        for key, approx_rows in row_count_map.items():
            table_id = f"table:{db_name}.{key}"
            if table_id in store.nodes:
                store.nodes[table_id]["approx_row_count"] = approx_rows

        # -- Columns -------------------------------------------------------
        columns = await conn.fetch(
            "SELECT table_schema, table_name, column_name, ordinal_position, "
            "       data_type, is_nullable, column_default "
            "FROM information_schema.columns "
            "WHERE table_schema NOT IN "
            "('pg_catalog', 'information_schema', 'pg_toast') "
            "ORDER BY table_schema, table_name, ordinal_position"
        )
        for row in columns:
            schema_name = row["table_schema"]
            table_name = row["table_name"]
            col_name: str = row["column_name"]
            fqn = f"{db_name}.{schema_name}.{table_name}.{col_name}"
            col_id = f"column:{fqn}"
            table_id = f"table:{db_name}.{schema_name}.{table_name}"

            store.add_node(
                col_id,
                "Column",
                col_name,
                table=table_name,
                schema=schema_name,
                database=db_name,
                data_type=row["data_type"],
                is_nullable=row["is_nullable"] == "YES",
                ordinal_position=row["ordinal_position"],
                column_default=row["column_default"],
            )
            store.add_edge(col_id, table_id, "BELONGS_TO")
            counts["columns"] += 1

    log.info("schema_ingestion_complete", **counts)
    return counts
