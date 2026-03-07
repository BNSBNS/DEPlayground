"""Periodic simulation: randomly mutate the knowledge graph."""

from __future__ import annotations

import asyncio
import random
import signal
from uuid import uuid4

import structlog

from src.ingestion.store import store
from simulation.seed import seed

log = structlog.get_logger(__name__)

TABLE_SCHEMAS = ["raw", "staging", "marts", "metrics"]
TABLE_PREFIXES = ["dim_", "fact_", "stg_", "int_", "rpt_", "agg_"]
TABLE_SUFFIXES = [
    "events", "snapshots", "history", "summary", "daily",
    "hourly", "metrics", "scores", "features", "logs",
]


def _random_table_name() -> str:
    prefix = random.choice(TABLE_PREFIXES)
    suffix = random.choice(TABLE_SUFFIXES)
    return f"{prefix}{random.choice(['user', 'order', 'product', 'session'])}_{suffix}"


def _add_random_table() -> None:
    """Add a new random table to the graph."""
    schema = random.choice(TABLE_SCHEMAS)
    name = _random_table_name()
    nid = str(uuid4())
    row_count = random.randint(100, 1_000_000)

    store.add_node(
        nid, "table", name,
        schema_name=schema,
        database="warehouse",
        row_count=row_count,
        description=f"Auto-generated table {name}",
    )

    # Link to a random existing schema node
    schema_nodes = store.get_nodes_by_type("schema")
    matching = [n for n in schema_nodes if n.get("name") == schema]
    if matching:
        store.add_edge(nid, matching[0]["id"], "belongs_to")

    log.info("table_added", name=name, schema=schema, row_count=row_count)


def _modify_random_description() -> None:
    """Update the description of a random table."""
    tables = store.get_nodes_by_type("table")
    if not tables:
        return
    table = random.choice(tables)
    old_desc = table.get("description", "")
    table["description"] = f"{old_desc} [Updated at simulation tick]"
    log.info("description_modified", table=table["name"])


async def run_simulation(interval: int = 60) -> None:
    """Run periodic graph mutations until cancelled."""
    log.info("simulation_starting", interval_s=interval)

    # Seed initial data if store is empty
    if not store.nodes:
        log.info("seeding_initial_data")
        seed()

    loop = asyncio.get_running_loop()
    stop = loop.create_future()

    def _signal_handler() -> None:
        if not stop.done():
            stop.set_result(None)

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:
            # Windows does not support add_signal_handler
            pass

    tick = 0
    while not stop.done():
        tick += 1
        action = random.choice(["add_table", "modify_description"])
        if action == "add_table":
            _add_random_table()
        else:
            _modify_random_description()

        log.info(
            "simulation_tick",
            tick=tick,
            action=action,
            total_nodes=len(store.nodes),
            total_edges=len(store.edges),
        )

        try:
            await asyncio.wait_for(asyncio.shield(stop), timeout=interval)
            break
        except TimeoutError:
            continue

    log.info("simulation_stopped", total_ticks=tick)


if __name__ == "__main__":
    asyncio.run(run_simulation())
