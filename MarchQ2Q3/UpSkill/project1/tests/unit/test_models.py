"""Tests for domain models."""

import pytest

from src.models.alerts import Alert, AlertState
from src.models.metrics import DataQualityMetric, MetricStatus, MetricType


class TestDataQualityMetric:
    def test_derive_status_healthy(self) -> None:
        metric = DataQualityMetric(
            table_name="t",
            database="db",
            metric_type=MetricType.FRESHNESS,
            value=30.0,
            threshold_warning=60.0,
            threshold_critical=120.0,
        )
        metric.derive_status()
        assert metric.status == MetricStatus.HEALTHY

    def test_derive_status_warning(self) -> None:
        metric = DataQualityMetric(
            table_name="t",
            database="db",
            metric_type=MetricType.FRESHNESS,
            value=80.0,
            threshold_warning=60.0,
            threshold_critical=120.0,
        )
        metric.derive_status()
        assert metric.status == MetricStatus.WARNING

    def test_derive_status_critical(self) -> None:
        metric = DataQualityMetric(
            table_name="t",
            database="db",
            metric_type=MetricType.FRESHNESS,
            value=150.0,
            threshold_warning=60.0,
            threshold_critical=120.0,
        )
        metric.derive_status()
        assert metric.status == MetricStatus.CRITICAL

    def test_derive_status_unknown_no_thresholds(self) -> None:
        metric = DataQualityMetric(
            table_name="t",
            database="db",
            metric_type=MetricType.FRESHNESS,
            value=50.0,
        )
        metric.derive_status()
        assert metric.status == MetricStatus.UNKNOWN


class TestAlert:
    def test_initial_state_is_open(self, sample_alert: Alert) -> None:
        assert sample_alert.state == AlertState.OPEN

    def test_transition_open_to_acknowledged(self, sample_alert: Alert) -> None:
        sample_alert.transition_to(AlertState.ACKNOWLEDGED)
        assert sample_alert.state == AlertState.ACKNOWLEDGED
        assert sample_alert.acknowledged_at is not None

    def test_transition_acknowledged_to_resolved(self, sample_alert: Alert) -> None:
        sample_alert.transition_to(AlertState.ACKNOWLEDGED)
        sample_alert.transition_to(AlertState.RESOLVED)
        assert sample_alert.state == AlertState.RESOLVED
        assert sample_alert.resolved_at is not None

    def test_invalid_transition_raises(self, sample_alert: Alert) -> None:
        sample_alert.transition_to(AlertState.RESOLVED)
        with pytest.raises(ValueError, match="Cannot transition"):
            sample_alert.transition_to(AlertState.OPEN)

    def test_can_transition_to(self, sample_alert: Alert) -> None:
        assert sample_alert.can_transition_to(AlertState.ACKNOWLEDGED)
        assert sample_alert.can_transition_to(AlertState.RESOLVED)
        assert not sample_alert.can_transition_to(AlertState.OPEN)
