"""Shared test fixtures."""

import pytest

from src.lineage.graph import LineageGraph
from src.models.alerts import Alert, AlertSeverity
from src.models.metrics import DataQualityMetric, MetricStatus, MetricType


@pytest.fixture
def sample_metric() -> DataQualityMetric:
    return DataQualityMetric(
        table_name="orders",
        database="ecommerce",
        schema_name="public",
        metric_type=MetricType.FRESHNESS,
        value=45.0,
        threshold_warning=60.0,
        threshold_critical=120.0,
        status=MetricStatus.HEALTHY,
    )


@pytest.fixture
def sample_alert() -> Alert:
    return Alert(
        title="Stale data: orders",
        description="Orders table has not been updated in 150 minutes",
        severity=AlertSeverity.CRITICAL,
        source_table="orders",
        source_metric_type="freshness",
    )


@pytest.fixture
def sample_lineage_graph() -> LineageGraph:
    """Build a simple test lineage graph.

    raw_orders → stg_orders → fct_orders → dashboard_revenue
    raw_customers → stg_customers → fct_orders
    """
    graph = LineageGraph()
    graph.add_edge("raw_orders", "stg_orders")
    graph.add_edge("stg_orders", "fct_orders")
    graph.add_edge("raw_customers", "stg_customers")
    graph.add_edge("stg_customers", "fct_orders")
    graph.add_edge("fct_orders", "dashboard_revenue")
    return graph
