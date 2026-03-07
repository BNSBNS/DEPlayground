from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import structlog

from src.ingestion.store import store

log = structlog.get_logger(__name__)


def ingest_dbt_manifest(path: Path) -> dict[str, Any]:
    """Parse a dbt manifest.json and create model nodes with lineage edges.

    Creates DbtModelNode for each entry in manifest["nodes"], plus edges:
      - SOURCES  -> source tables
      - REFS     -> referenced dbt models
      - MATERIALIZES -> target table
    """
    manifest = json.loads(path.read_text(encoding="utf-8"))
    nodes_raw: dict[str, Any] = manifest.get("nodes", {})

    counts = {"models": 0, "sources_edges": 0, "refs_edges": 0, "materializes_edges": 0}

    for unique_id, node_data in nodes_raw.items():
        resource_type = node_data.get("resource_type", "")
        if resource_type != "model":
            continue

        name: str = node_data.get("name", unique_id)
        model_id = f"dbt_model:{unique_id}"

        store.add_node(
            model_id,
            "DbtModel",
            name,
            unique_id=unique_id,
            schema=node_data.get("schema", ""),
            database=node_data.get("database", ""),
            description=node_data.get("description", ""),
            materialized=node_data.get("config", {}).get("materialized", ""),
            tags=node_data.get("tags", []),
            package_name=node_data.get("package_name", ""),
        )
        counts["models"] += 1

        # SOURCES edges -- model depends on source tables
        for source in node_data.get("sources", []):
            if isinstance(source, list) and len(source) >= 2:
                source_name, table_name = source[0], source[1]
                source_id = f"source:{source_name}.{table_name}"
                # Ensure the source node exists (lightweight placeholder).
                if source_id not in store.nodes:
                    store.add_node(
                        source_id, "Source", f"{source_name}.{table_name}"
                    )
                store.add_edge(model_id, source_id, "SOURCES")
                counts["sources_edges"] += 1

        # REFS edges -- model references other models
        for ref in node_data.get("refs", []):
            ref_name = ref.get("name", "") if isinstance(ref, dict) else ref
            if not ref_name:
                continue
            # Try to resolve a concrete node id; fall back to a name-based id.
            ref_id = _resolve_ref(ref_name, nodes_raw)
            store.add_edge(model_id, ref_id, "REFS")
            counts["refs_edges"] += 1

        # MATERIALIZES edge -- model writes to a target table
        db = node_data.get("database", "")
        schema = node_data.get("schema", "")
        relation_name = node_data.get("relation_name") or node_data.get("alias", name)
        if schema:
            fqn = f"{db}.{schema}.{relation_name}" if db else f"{schema}.{relation_name}"
            table_id = f"table:{fqn}"
            store.add_edge(model_id, table_id, "MATERIALIZES")
            counts["materializes_edges"] += 1

    log.info("dbt_ingestion_complete", path=str(path), **counts)
    return counts


def _resolve_ref(ref_name: str, nodes_raw: dict[str, Any]) -> str:
    """Best-effort resolution of a ref name to a dbt_model node id."""
    for uid, data in nodes_raw.items():
        if data.get("resource_type") == "model" and data.get("name") == ref_name:
            return f"dbt_model:{uid}"
    return f"dbt_model:{ref_name}"
