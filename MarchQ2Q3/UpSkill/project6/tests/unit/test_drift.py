from __future__ import annotations

import numpy as np
import pytest

from src.monitoring.drift import (
    DriftSeverity,
    compute_chi_squared,
    compute_psi,
    detect_categorical_drift,
    detect_numeric_drift,
)


class TestComputePSI:
    def test_identical_distributions(self) -> None:
        data = list(np.random.normal(0, 1, 1000))
        psi = compute_psi(data, data)
        assert psi < 0.01  # Essentially zero

    def test_similar_distributions(self) -> None:
        ref = list(np.random.normal(0, 1, 1000))
        cur = list(np.random.normal(0.1, 1, 1000))
        psi = compute_psi(ref, cur)
        assert psi < 0.1  # Minor shift

    def test_shifted_distribution(self) -> None:
        ref = list(np.random.normal(0, 1, 1000))
        cur = list(np.random.normal(2, 1, 1000))
        psi = compute_psi(ref, cur)
        assert psi > 0.1  # Significant shift

    def test_very_different_distributions(self) -> None:
        ref = list(np.random.normal(0, 1, 1000))
        cur = list(np.random.normal(5, 0.5, 1000))
        psi = compute_psi(ref, cur)
        assert psi > 0.2  # Critical shift

    def test_empty_reference(self) -> None:
        psi = compute_psi([], [1.0, 2.0])
        assert psi == 0.0

    def test_empty_current(self) -> None:
        psi = compute_psi([1.0, 2.0], [])
        assert psi == 0.0

    def test_psi_non_negative(self) -> None:
        ref = list(np.random.uniform(0, 10, 500))
        cur = list(np.random.uniform(2, 12, 500))
        psi = compute_psi(ref, cur)
        assert psi >= 0.0


class TestComputeChiSquared:
    def test_identical_distributions(self) -> None:
        dist = {"a": 100, "b": 200, "c": 300}
        chi2, p = compute_chi_squared(dist, dist)
        assert chi2 == pytest.approx(0.0, abs=0.01)
        assert p > 0.05

    def test_different_distributions(self) -> None:
        ref = {"a": 100, "b": 200, "c": 300}
        cur = {"a": 300, "b": 100, "c": 200}
        chi2, p = compute_chi_squared(ref, cur)
        assert chi2 > 0
        assert p < 0.05

    def test_new_category(self) -> None:
        ref = {"a": 100, "b": 200}
        cur = {"a": 100, "b": 200, "c": 50}
        chi2, p = compute_chi_squared(ref, cur)
        assert chi2 >= 0

    def test_single_category(self) -> None:
        ref = {"a": 100}
        cur = {"a": 200}
        chi2, p = compute_chi_squared(ref, cur)
        assert chi2 == 0.0
        assert p == 1.0


class TestDetectNumericDrift:
    def test_no_drift(self) -> None:
        np.random.seed(42)
        ref = list(np.random.normal(0, 1, 1000))
        cur = list(np.random.normal(0, 1, 1000))
        result = detect_numeric_drift("test_feature", ref, cur)
        assert result.severity == DriftSeverity.NONE

    def test_warning_drift(self) -> None:
        np.random.seed(42)
        ref = list(np.random.normal(0, 1, 1000))
        cur = list(np.random.normal(1.0, 1, 1000))
        result = detect_numeric_drift("test_feature", ref, cur)
        assert result.severity in (DriftSeverity.WARNING, DriftSeverity.CRITICAL)
        assert result.metric == "psi"

    def test_critical_drift(self) -> None:
        np.random.seed(42)
        ref = list(np.random.normal(0, 1, 1000))
        cur = list(np.random.normal(5, 0.5, 1000))
        result = detect_numeric_drift("test_feature", ref, cur)
        assert result.severity == DriftSeverity.CRITICAL
        assert result.value > 0.2

    def test_result_details(self) -> None:
        ref = [1.0, 2.0, 3.0]
        cur = [4.0, 5.0, 6.0]
        result = detect_numeric_drift("test", ref, cur)
        assert "reference_count" in result.details
        assert "current_count" in result.details
        assert result.details["reference_count"] == 3
        assert result.details["current_count"] == 3


class TestDetectCategoricalDrift:
    def test_no_drift(self) -> None:
        ref = {"a": 100, "b": 200, "c": 300}
        result = detect_categorical_drift("test", ref, ref)
        assert result.severity == DriftSeverity.NONE
        assert result.metric == "chi_squared"

    def test_significant_drift(self) -> None:
        ref = {"a": 100, "b": 200, "c": 300}
        cur = {"a": 300, "b": 50, "c": 50}
        result = detect_categorical_drift("test", ref, cur)
        assert result.severity != DriftSeverity.NONE
        assert "p_value" in result.details

    def test_to_dict(self) -> None:
        ref = {"a": 100, "b": 200}
        result = detect_categorical_drift("test", ref, ref)
        d = result.to_dict()
        assert "feature_name" in d
        assert "metric" in d
        assert "severity" in d
        assert "value" in d
