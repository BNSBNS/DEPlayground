from __future__ import annotations

from enum import Enum
from typing import Any

import numpy as np
import structlog

from src.config import get_settings

logger = structlog.get_logger(__name__)


def _thresholds() -> tuple[float, float, float]:
    """Return (psi_warning, psi_critical, chi2_p_threshold) from config.

    Reading from config at call time (not import time) means MONITORING_*
    environment variables are respected even if set after module import.
    """
    m = get_settings().monitoring
    return m.psi_warning, m.psi_critical, m.chi2_p_threshold


# Keep module-level aliases for backwards-compatibility and easy reference
PSI_WARNING = 0.1
PSI_CRITICAL = 0.2
CHI2_P_THRESHOLD = 0.05


class DriftSeverity(str, Enum):
    NONE = "none"
    WARNING = "warning"
    CRITICAL = "critical"


class DriftResult:
    def __init__(
        self,
        feature_name: str,
        metric: str,
        value: float,
        severity: DriftSeverity,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.feature_name = feature_name
        self.metric = metric
        self.value = value
        self.severity = severity
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature_name": self.feature_name,
            "metric": self.metric,
            "value": round(self.value, 6),
            "severity": self.severity.value,
            "details": self.details,
        }


def compute_psi(
    reference: list[float],
    current: list[float],
    bins: int = 10,
) -> float:
    """Compute Population Stability Index between two distributions."""
    if not reference or not current:
        return 0.0

    ref_arr = np.array(reference, dtype=np.float64)
    cur_arr = np.array(current, dtype=np.float64)

    # Create bins from reference distribution
    bin_edges = np.histogram_bin_edges(ref_arr, bins=bins)
    ref_counts, _ = np.histogram(ref_arr, bins=bin_edges)
    cur_counts, _ = np.histogram(cur_arr, bins=bin_edges)

    # Normalize to proportions, add small epsilon to avoid log(0)
    eps = 1e-10
    ref_pct = ref_counts / max(ref_counts.sum(), 1) + eps
    cur_pct = cur_counts / max(cur_counts.sum(), 1) + eps

    psi = float(np.sum((cur_pct - ref_pct) * np.log(cur_pct / ref_pct)))
    return psi


def compute_chi_squared(
    reference_dist: dict[str, int],
    current_dist: dict[str, int],
) -> tuple[float, float]:
    """Compute chi-squared statistic for categorical distributions."""
    from scipy.stats import chi2_contingency

    all_keys = sorted(set(reference_dist) | set(current_dist))
    if len(all_keys) < 2:
        return 0.0, 1.0

    ref_counts = [reference_dist.get(k, 0) for k in all_keys]
    cur_counts = [current_dist.get(k, 0) for k in all_keys]

    observed = np.array([ref_counts, cur_counts])

    # Avoid zero rows/cols
    col_sums = observed.sum(axis=0)
    nonzero_mask = col_sums > 0
    if nonzero_mask.sum() < 2:
        return 0.0, 1.0

    observed = observed[:, nonzero_mask]
    chi2, p_value, _, _ = chi2_contingency(observed)
    return float(chi2), float(p_value)


def detect_numeric_drift(
    feature_name: str,
    reference: list[float],
    current: list[float],
) -> DriftResult:
    psi = compute_psi(reference, current)
    psi_warning, psi_critical, _ = _thresholds()

    if psi >= psi_critical:
        severity = DriftSeverity.CRITICAL
    elif psi >= psi_warning:
        severity = DriftSeverity.WARNING
    else:
        severity = DriftSeverity.NONE

    result = DriftResult(
        feature_name=feature_name,
        metric="psi",
        value=psi,
        severity=severity,
        details={
            "reference_count": len(reference),
            "current_count": len(current),
            "reference_mean": float(np.mean(reference)) if reference else 0.0,
            "current_mean": float(np.mean(current)) if current else 0.0,
        },
    )

    if severity != DriftSeverity.NONE:
        logger.warning(
            "drift_detected",
            feature=feature_name,
            psi=round(psi, 4),
            severity=severity.value,
        )

    return result


def detect_categorical_drift(
    feature_name: str,
    reference_dist: dict[str, int],
    current_dist: dict[str, int],
) -> DriftResult:
    chi2, p_value = compute_chi_squared(reference_dist, current_dist)
    _, _, chi2_p_threshold = _thresholds()

    if p_value < chi2_p_threshold:
        severity = DriftSeverity.CRITICAL if p_value < 0.01 else DriftSeverity.WARNING
    else:
        severity = DriftSeverity.NONE

    return DriftResult(
        feature_name=feature_name,
        metric="chi_squared",
        value=chi2,
        severity=severity,
        details={"p_value": p_value},
    )
