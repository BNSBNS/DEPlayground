from __future__ import annotations

from pathlib import Path
from typing import Any

import structlog
import yaml

from src.ingestion.store import store

log = structlog.get_logger(__name__)


def ingest_owners(path: Path) -> dict[str, Any]:
    """Parse a YAML file of teams/owners and create Owner nodes.

    Expected YAML format::

        owners:
          - name: Alice Smith
            team: Data Engineering
            email: alice@example.com
            role: lead
          - name: Bob Jones
            team: Analytics
            ...

    Or a flat list at the top level.
    """
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    entries: list[dict[str, Any]] = (
        raw if isinstance(raw, list) else raw.get("owners", raw.get("teams", []))
    )

    counts = {"owners": 0}

    for entry in entries:
        name: str = entry.get("name", "")
        if not name:
            log.warning("skipping_owner", reason="missing name", entry=entry)
            continue

        owner_id = f"owner:{name}"
        store.add_node(
            owner_id,
            "Owner",
            name,
            team=entry.get("team", ""),
            email=entry.get("email", ""),
            role=entry.get("role", ""),
        )
        counts["owners"] += 1

    log.info("owner_ingestion_complete", path=str(path), **counts)
    return counts
