"""Parse lineage definitions from YAML or dbt manifest."""

import json
from pathlib import Path
from typing import Any

from src.lineage.graph import LineageGraph
from src.logging import get_logger

logger = get_logger(__name__)


def parse_lineage_yaml(path: Path) -> LineageGraph:
    """Parse lineage from a YAML file.

    Expected format:
        tables:
          orders:
            upstream: [raw_orders, customers]
          revenue:
            upstream: [orders, payments]
    """
    import yaml  # noqa: PLC0415

    with path.open() as f:
        data: dict[str, Any] = yaml.safe_load(f)

    graph = LineageGraph()
    for table, spec in data.get("tables", {}).items():
        for upstream in spec.get("upstream", []):
            graph.add_edge(upstream, table)
    logger.info("Parsed lineage YAML", path=str(path), nodes=len(graph.all_nodes()))
    return graph


def parse_dbt_manifest(path: Path) -> LineageGraph:
    """Parse lineage from a dbt manifest.json file."""
    with path.open() as f:
        manifest: dict[str, Any] = json.load(f)

    graph = LineageGraph()
    for node_id, node_data in manifest.get("nodes", {}).items():
        node_name = node_data.get("name", node_id)
        for dep in node_data.get("depends_on", {}).get("nodes", []):
            dep_name = manifest.get("nodes", {}).get(dep, {}).get("name", dep)
            graph.add_edge(dep_name, node_name)

    logger.info("Parsed dbt manifest", path=str(path), nodes=len(graph.all_nodes()))
    return graph
