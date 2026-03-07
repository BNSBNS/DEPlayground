"""OpenLineage event collector — keeps the in-memory lineage graph up to date.

Called from the webhook endpoint at POST /api/v1/webhooks/openlineage.

Learning note:
  OpenLineage is an open standard for pipeline lineage metadata.
  Each run event tells us: "job X consumed tables A,B and produced table C."
  We translate that into directed edges in our in-memory LineageGraph:
    A → C   (A feeds into C)
    B → C
  These edges are then used by the RCA engine (BFS upstream walk).
"""

from __future__ import annotations

from src.lineage.graph import get_lineage_graph
from src.logging import get_logger

logger = get_logger(__name__)


def handle_event(
    event_type: str,
    job_name: str,
    inputs: list[dict[str, object]],
    outputs: list[dict[str, object]],
) -> int:
    """Process an OpenLineage run event and update the lineage graph.

    Only COMPLETE events carry reliable lineage (START may have partial info,
    FAIL events tell us what broke but not what was produced).

    Args:
        event_type: "START", "COMPLETE", or "FAIL".
        job_name: Identifier of the pipeline job.
        inputs: List of input dataset dicts with 'namespace' and 'name' keys.
        outputs: List of output dataset dicts with 'namespace' and 'name' keys.

    Returns:
        Number of lineage edges added (0 for non-COMPLETE events).
    """
    if event_type != "COMPLETE":
        logger.info("openlineage_event_skipped", event_type=event_type, job=job_name)
        return 0

    graph = get_lineage_graph()
    edges_added = 0

    for inp in inputs:
        upstream = _dataset_name(inp)
        for out in outputs:
            downstream = _dataset_name(out)
            if upstream and downstream and upstream != downstream:
                graph.add_edge(upstream, downstream)
                edges_added += 1
                logger.info("lineage_edge_added", upstream=upstream, downstream=downstream)

    logger.info(
        "openlineage_event_processed",
        job=job_name,
        inputs=len(inputs),
        outputs=len(outputs),
        edges_added=edges_added,
    )
    return edges_added


def _dataset_name(dataset: dict[str, object]) -> str | None:
    """Build a qualified name from OpenLineage dataset dict: 'namespace.name'."""
    namespace = str(dataset.get("namespace", "")).strip()
    name = str(dataset.get("name", "")).strip()
    if not name:
        return None
    return f"{namespace}.{name}" if namespace else name
