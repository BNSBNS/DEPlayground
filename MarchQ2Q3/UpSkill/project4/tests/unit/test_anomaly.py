from __future__ import annotations

from src.processors.anomaly_detector import (
    CLICKS_PER_MINUTE_THRESHOLD,
    ORDER_AMOUNT_MULTIPLIER,
    PAYMENT_FAILURE_THRESHOLD,
    AnomalyDetector,
)


class TestAnomalyDetectorRules:
    """Test anomaly detection rules using static helper methods."""

    def test_high_value_order_above_threshold(self) -> None:
        avg = 100.0
        amount = avg * ORDER_AMOUNT_MULTIPLIER + 1
        assert AnomalyDetector.is_high_value_order(amount, avg) is True

    def test_high_value_order_below_threshold(self) -> None:
        avg = 100.0
        amount = avg * ORDER_AMOUNT_MULTIPLIER - 1
        assert AnomalyDetector.is_high_value_order(amount, avg) is False

    def test_high_value_order_exactly_at_threshold(self) -> None:
        avg = 100.0
        amount = avg * ORDER_AMOUNT_MULTIPLIER
        assert AnomalyDetector.is_high_value_order(amount, avg) is False

    def test_high_value_order_zero_avg(self) -> None:
        assert AnomalyDetector.is_high_value_order(1.0, 0.0) is False

    def test_click_flood_above_threshold(self) -> None:
        assert AnomalyDetector.is_click_flood(CLICKS_PER_MINUTE_THRESHOLD + 1) is True

    def test_click_flood_below_threshold(self) -> None:
        assert AnomalyDetector.is_click_flood(CLICKS_PER_MINUTE_THRESHOLD - 1) is False

    def test_click_flood_at_threshold(self) -> None:
        assert AnomalyDetector.is_click_flood(CLICKS_PER_MINUTE_THRESHOLD) is False

    def test_click_flood_zero(self) -> None:
        assert AnomalyDetector.is_click_flood(0) is False

    def test_payment_failure_spike_above_threshold(self) -> None:
        assert (
            AnomalyDetector.is_payment_failure_spike(PAYMENT_FAILURE_THRESHOLD + 1)
            is True
        )

    def test_payment_failure_spike_at_threshold(self) -> None:
        assert (
            AnomalyDetector.is_payment_failure_spike(PAYMENT_FAILURE_THRESHOLD)
            is True
        )

    def test_payment_failure_spike_below_threshold(self) -> None:
        assert (
            AnomalyDetector.is_payment_failure_spike(PAYMENT_FAILURE_THRESHOLD - 1)
            is False
        )

    def test_payment_failure_zero(self) -> None:
        assert AnomalyDetector.is_payment_failure_spike(0) is False


class TestAnomalyDetectorThresholds:
    """Verify threshold constants are sensible."""

    def test_order_multiplier_is_positive(self) -> None:
        assert ORDER_AMOUNT_MULTIPLIER > 0

    def test_click_threshold_is_positive(self) -> None:
        assert CLICKS_PER_MINUTE_THRESHOLD > 0

    def test_payment_failure_threshold_minimum(self) -> None:
        assert PAYMENT_FAILURE_THRESHOLD >= 2
