"""Tests for data quality detectors."""

from src.detectors.volume import compute_zscore


class TestZScore:
    def test_zscore_normal(self) -> None:
        values = [100.0, 102.0, 98.0, 101.0, 99.0]
        z = compute_zscore(100.0, values)
        assert z is not None
        assert abs(z) < 1.0

    def test_zscore_anomaly(self) -> None:
        values = [100.0, 102.0, 98.0, 101.0, 99.0]
        z = compute_zscore(200.0, values)
        assert z is not None
        assert abs(z) > 3.0

    def test_zscore_insufficient_data(self) -> None:
        assert compute_zscore(100.0, [100.0, 101.0]) is None

    def test_zscore_zero_std(self) -> None:
        values = [100.0, 100.0, 100.0]
        z = compute_zscore(100.0, values)
        assert z == 0.0

    def test_zscore_empty(self) -> None:
        assert compute_zscore(100.0, []) is None
