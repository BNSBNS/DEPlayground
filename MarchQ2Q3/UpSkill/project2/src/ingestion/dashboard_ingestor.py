from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import structlog

from src.ingestion.store import store

log = structlog.get_logger(__name__)


def ingest_dashboards(path: Path) -> dict[str, Any]:
    """Parse a dashboards JSON file and create graph nodes + edges.

    Expected format -- a list of objects, each with:
        name, tool, url, owner, tables_used: list[str]

    Creates:
      - DashboardNode per dashboard
      - USES edges to Table nodes
      - OWNED_BY edges to Owner nodes
    """
    raw = json.loads(path.read_text(encoding="utf-8"))
    dashboards: list[dict[str, Any]] = raw if isinstance(raw, list) else raw.get("dashboards", [])

    counts = {"dashboards": 0, "uses_edges": 0, "owned_by_edges": 0}

    for entry in dashboards:
        name: str = entry.get("name", "")
        if not name:
            log.warning("skipping_dashboard", reason="missing name", entry=entry)
            continue

        dash_id = f"dashboard:{name}"
        store.add_node(
            dash_id,
            "Dashboard",
            name,
            tool=entry.get("tool", ""),
            url=entry.get("url", ""),
        )
        counts["dashboards"] += 1

        # USES edges -> tables
        for table_ref in entry.get("tables_used", []):
            table_id = f"table:{table_ref}"
            store.add_edge(dash_id, table_id, "USES")
            counts["uses_edges"] += 1

        # OWNED_BY edge -> owner
        owner: str = entry.get("owner", "")
        if owner:
            owner_id = f"owner:{owner}"
            if owner_id not in store.nodes:
                store.add_node(owner_id, "Owner", owner)
            store.add_edge(dash_id, owner_id, "OWNED_BY")
            counts["owned_by_edges"] += 1

    log.info("dashboard_ingestion_complete", path=str(path), **counts)
    return counts
