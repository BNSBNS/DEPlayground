"""Root Cause Analysis engine — BFS upstream walk with confidence scoring."""

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    import asyncpg

from src.config import get_settings
from src.lineage.graph import get_lineage_graph
from src.logging import get_logger

logger = get_logger(__name__)


class RCAResult(BaseModel):
    """Result of root cause analysis for a single upstream node."""

    dataset: str
    depth: int
    has_active_alerts: bool
    alert_count: int = 0
    is_likely_root: bool = False
    confidence: float = 0.0
    evidence: list[str] = []
    suggested_actions: list[str] = []


async def find_root_cause(
    source_table: str,
    pool: asyncpg.Pool[asyncpg.Record],
) -> list[RCAResult]:
    """Walk upstream from the failing dataset, check for active alerts.

    The deepest upstream node with active alerts is the probable root cause.
    Confidence: 0.6 base for self-origin, +0.1 per corroborating upstream alert.
    """
    settings = get_settings()
    graph = get_lineage_graph()

    if not graph.has_node(source_table):
        return [
            RCAResult(
                dataset=source_table,
                depth=0,
                has_active_alerts=True,
                is_likely_root=True,
                confidence=settings.rca.base_confidence,
                evidence=[f"No lineage data for {source_table}; self-origin assumed"],
                suggested_actions=["Check data source directly"],
            )
        ]

    # BFS upstream, track depth
    results: list[RCAResult] = []
    visited: set[str] = set()
    queue: deque[tuple[str, int]] = deque([(source_table, 0)])

    while queue:
        node, depth = queue.popleft()
        if node in visited:
            continue
        visited.add(node)

        # Check for active alerts on this node
        alert_count = await pool.fetchval(
            """
            SELECT COUNT(*) FROM alerts
            WHERE source_table = $1 AND state IN ('open', 'acknowledged')
            """,
            node,
        )

        result = RCAResult(
            dataset=node,
            depth=depth,
            has_active_alerts=alert_count > 0,
            alert_count=alert_count,
        )
        if alert_count > 0:
            result.evidence.append(f"{alert_count} active alert(s) on {node}")
        results.append(result)

        # Continue upstream
        for upstream in graph._upstream.get(node, set()):
            if upstream not in visited:
                queue.append((upstream, depth + 1))

    # Score: deepest upstream node with alerts is root cause
    nodes_with_alerts = [r for r in results if r.has_active_alerts]

    if not nodes_with_alerts:
        # Self-origin
        for r in results:
            if r.depth == 0:
                r.is_likely_root = True
                r.confidence = settings.rca.base_confidence
                r.evidence.append("No upstream alerts found; self-origin")
        return results

    # Deepest upstream with alerts is root cause
    nodes_with_alerts.sort(key=lambda r: r.depth, reverse=True)
    root = nodes_with_alerts[0]
    root.is_likely_root = True

    # Confidence: base + increment per corroborating alert
    corroborating = len(nodes_with_alerts) - 1
    root.confidence = min(
        settings.rca.base_confidence + corroborating * settings.rca.confidence_increment,
        settings.rca.max_confidence,
    )
    root.suggested_actions.append(f"Investigate {root.dataset} first — deepest upstream failure")

    return results
