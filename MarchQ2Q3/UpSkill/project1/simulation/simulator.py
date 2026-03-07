"""Continuous simulator — drives the full observability pipeline for study/demo.

What this does every 30 seconds:
  1. Runs 4 quality checks (one per simulated table, one detector type each)
  2. For each check, randomly decides: healthy (70%), warning (15%), critical (15%)
  3. For real detectors (freshness, distribution):
       → Injects an anomaly into the DB before running the check
       → Runs the actual detector against the live table
       → Restores healthy state after the check
  4. For synthetic detectors (volume, schema):
       → Constructs a DataQualityMetric directly with appropriate values
  5. Saves every metric to data_quality_metrics
  6. On warning/critical: creates an open alert in the alerts table
  7. On critical: runs the BFS root-cause analysis (RCA) and updates the alert

Study guide — trace this execution path:
  sim_events   → src/detectors/freshness.py     → staleness in minutes
  sim_orders   → (synthetic)                    → z-score volume anomaly
  sim_sales    → (synthetic)                    → schema diff
  sim_products → src/detectors/distribution.py → KS-test distribution shift
  Any critical → src/reasoning/rca.py           → BFS upstream walk

Run:
    python -m simulation.simulator
    make simulate
"""

from __future__ import annotations

import asyncio
import random
import uuid
from datetime import datetime, timezone

import asyncpg

from src.alerting.router import route_alert
from src.config import get_settings
from src.db.pool import create_tables, save_metric
from src.detectors.distribution import check_distribution
from src.detectors.freshness import check_freshness
from src.lineage.graph import LineageGraph, set_lineage_graph
from src.logging import configure_logging, get_logger
from src.models.alerts import Alert, AlertSeverity, AlertState
from src.models.metrics import DataQualityMetric, MetricStatus, MetricType
from src.reasoning.rca import find_root_cause

logger = get_logger(__name__)

TICK_INTERVAL_SECONDS = 30
SCENARIOS = ["healthy", "warning", "critical"]
WEIGHTS = [70, 15, 15]

# How many minutes stale to inject per scenario
FRESHNESS_STALE_MINUTES = {"healthy": 5, "warning": 90, "critical": 150}

# Z-scores to simulate for volume (bypasses DB row manipulation)
VOLUME_ZSCORES = {"healthy": 0.3, "warning": 2.4, "critical": 3.6}

# Outlier price for distribution injection (normal range: $10–$500)
OUTLIER_PRICE = 99_999.0
OUTLIER_COUNT = 100


# ── Alert helpers ─────────────────────────────────────────────────────────────

async def _save_alert(pool: asyncpg.Pool, alert: Alert) -> None:
    await pool.execute(
        """
        INSERT INTO alerts
            (id, title, description, severity, state, source_table,
             source_metric_type, root_cause, suggested_remediation, created_at)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
        """,
        alert.id, alert.title, alert.description, alert.severity.value,
        alert.state.value, alert.source_table, alert.source_metric_type,
        alert.root_cause, alert.suggested_remediation, alert.created_at,
    )


async def _patch_alert_rca(
    pool: asyncpg.Pool, alert_id: uuid.UUID, root_cause: str, remediation: str
) -> None:
    await pool.execute(
        "UPDATE alerts SET root_cause=$1, suggested_remediation=$2 WHERE id=$3",
        root_cause, remediation, alert_id,
    )


def _make_alert(metric: DataQualityMetric) -> Alert:
    severity = (
        AlertSeverity.CRITICAL if metric.status == MetricStatus.CRITICAL else AlertSeverity.WARNING
    )
    return Alert(
        title=f"{metric.table_name} {metric.metric_type.value} {metric.status.value.upper()}",
        description=(
            f"{metric.metric_type.value.title()} check on {metric.schema_name}.{metric.table_name}: "
            f"value={metric.value:.4g}, "
            f"warning_threshold={metric.threshold_warning}, critical_threshold={metric.threshold_critical}."
        ),
        severity=severity,
        state=AlertState.OPEN,
        source_table=metric.table_name,
        source_metric_type=metric.metric_type.value,
        created_at=datetime.now(tz=timezone.utc),
    )


# ── Synthetic metric builders ─────────────────────────────────────────────────

def _volume_metric(baseline: int, scenario: str) -> DataQualityMetric:
    zscore = VOLUME_ZSCORES[scenario]
    std = baseline * 0.10
    row_count = max(0, int(baseline - zscore * std))
    status = (
        MetricStatus.HEALTHY if zscore < 2.0
        else (MetricStatus.WARNING if zscore < 3.0 else MetricStatus.CRITICAL)
    )
    return DataQualityMetric(
        table_name="sim_orders", database="default", schema_name="public",
        metric_type=MetricType.VOLUME,
        value=float(row_count),
        threshold_warning=2.0, threshold_critical=3.0,
        status=status,
        metadata={"zscore": zscore, "historical_count": 30, "lookback_days": 14},
        measured_at=datetime.now(tz=timezone.utc),
    )


def _schema_metric(scenario: str) -> DataQualityMetric:
    if scenario == "healthy":
        changes, added, removed = 0, [], []
        status = MetricStatus.HEALTHY
    elif scenario == "warning":
        changes, added, removed = 1, ["discount_pct"], []  # addition → warning
        status = MetricStatus.WARNING
    else:
        changes, added, removed = 1, [], ["legacy_id"]   # removal → critical
        status = MetricStatus.CRITICAL
    return DataQualityMetric(
        table_name="sim_sales", database="default", schema_name="public",
        metric_type=MetricType.SCHEMA,
        value=float(changes),
        status=status,
        metadata={"added": added, "removed": removed, "type_changed": []},
        measured_at=datetime.now(tz=timezone.utc),
    )


# ── Real detectors ────────────────────────────────────────────────────────────

async def _freshness_check(pool: asyncpg.Pool, scenario: str) -> DataQualityMetric:
    stale = FRESHNESS_STALE_MINUTES[scenario]
    await pool.execute(
        "UPDATE sim_events SET updated_at = NOW() - ($1 || ' minutes')::INTERVAL",
        str(stale),
    )
    metric = await check_freshness(pool, table="sim_events", timestamp_column="updated_at")
    await pool.execute("UPDATE sim_events SET updated_at = NOW()")  # restore
    return metric


async def _distribution_check(
    pool: asyncpg.Pool, scenario: str, reference_prices: list[float]
) -> DataQualityMetric:
    if scenario != "healthy":
        # Inject extreme prices — KS test will flag the distribution shift
        outliers = [
            (f"Outlier-{i}", "Luxury", OUTLIER_PRICE + random.uniform(-1000, 1000), 0)
            for i in range(OUTLIER_COUNT)
        ]
        await pool.executemany(
            "INSERT INTO sim_products (name, category, price, stock) VALUES ($1,$2,$3,$4)",
            outliers,
        )
    metric = await check_distribution(
        pool, table="sim_products", column="price", reference_values=reference_prices
    )
    if scenario != "healthy":
        await pool.execute("DELETE FROM sim_products WHERE price > $1", OUTLIER_PRICE * 0.5)
    return metric


# ── RCA ───────────────────────────────────────────────────────────────────────

async def _run_rca(pool: asyncpg.Pool, alert: Alert) -> None:
    results = await find_root_cause(source_table=alert.source_table, pool=pool)
    root = next((r for r in results if r.is_likely_root), None)
    if not root:
        return
    root_cause = (
        f"Likely root: {root.dataset} "
        f"(depth={root.depth}, confidence={root.confidence:.0%}, alerts={root.alert_count})"
    )
    remediation = "; ".join(root.suggested_actions) or "Investigate root dataset directly"
    await _patch_alert_rca(pool, alert.id, root_cause, remediation)
    logger.info("rca_complete", root=root.dataset, confidence=root.confidence)


# ── Tick ──────────────────────────────────────────────────────────────────────

async def _tick(
    pool: asyncpg.Pool,
    tick: int,
    order_baseline: int,
    reference_prices: list[float],
) -> None:
    print(f"\n── Tick {tick} @ {datetime.now(tz=timezone.utc).strftime('%H:%M:%S')} UTC ──")
    ICONS = {MetricStatus.HEALTHY: "✓", MetricStatus.WARNING: "⚠", MetricStatus.CRITICAL: "✗"}

    for detector, scenario in [
        ("freshness",    random.choices(SCENARIOS, weights=WEIGHTS)[0]),
        ("volume",       random.choices(SCENARIOS, weights=WEIGHTS)[0]),
        ("schema",       random.choices(SCENARIOS, weights=WEIGHTS)[0]),
        ("distribution", random.choices(SCENARIOS, weights=WEIGHTS)[0]),
    ]:
        if detector == "freshness":
            metric = await _freshness_check(pool, scenario)
        elif detector == "volume":
            metric = _volume_metric(order_baseline, scenario)
        elif detector == "schema":
            metric = _schema_metric(scenario)
        else:
            metric = await _distribution_check(pool, scenario, reference_prices)

        await save_metric(pool, metric)
        icon = ICONS.get(metric.status, "?")
        print(f"  {icon} {detector:12s} | {metric.table_name:16s} | {metric.status.value}")

        if metric.status in (MetricStatus.WARNING, MetricStatus.CRITICAL):
            alert = _make_alert(metric)
            await _save_alert(pool, alert)
            await route_alert(alert)
            if metric.status == MetricStatus.CRITICAL:
                await _run_rca(pool, alert)


# ── Startup ───────────────────────────────────────────────────────────────────

async def _load_lineage(pool: asyncpg.Pool) -> None:
    rows = await pool.fetch("SELECT source_id, target_id FROM lineage_edges")
    graph = LineageGraph()
    for row in rows:
        graph.add_edge(row["source_id"], row["target_id"])
    set_lineage_graph(graph)
    logger.info("lineage_loaded", edges=len(rows))


async def _sample_reference_prices(pool: asyncpg.Pool) -> list[float]:
    rows = await pool.fetch(
        "SELECT price::DOUBLE PRECISION FROM sim_products WHERE price < $1 LIMIT 5000",
        OUTLIER_PRICE * 0.5,
    )
    return [float(r["price"]) for r in rows]


# ── Main ──────────────────────────────────────────────────────────────────────

async def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_json_format)

    pool: asyncpg.Pool = await asyncpg.create_pool(
        dsn=settings.postgres.get_dsn(), min_size=2, max_size=5
    )
    try:
        await create_tables(pool)
        await _load_lineage(pool)

        reference_prices = await _sample_reference_prices(pool)
        order_baseline = await pool.fetchval("SELECT COUNT(*) FROM sim_orders") or 2000

        if len(reference_prices) < 30 or order_baseline == 0:
            print("WARNING: Run `make seed` first — simulated tables are empty.")

        print(
            f"\nSimulator running — {TICK_INTERVAL_SECONDS}s ticks | "
            f"{WEIGHTS[0]}% healthy / {WEIGHTS[1]}% warning / {WEIGHTS[2]}% critical\n"
            f"Checks: freshness·volume·schema·distribution  |  Ctrl+C to stop\n"
            f"{'─' * 70}"
        )

        tick = 0
        while True:
            tick += 1
            try:
                await _tick(pool, tick, int(order_baseline), reference_prices)
            except Exception:
                logger.exception("tick_failed", tick=tick)
            await asyncio.sleep(TICK_INTERVAL_SECONDS)

    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
