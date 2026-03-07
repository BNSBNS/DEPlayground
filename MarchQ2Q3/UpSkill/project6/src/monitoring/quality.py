from __future__ import annotations

from datetime import datetime
from typing import Any

import numpy as np
import structlog

from src.models.stats import FeatureStats

logger = structlog.get_logger(__name__)


class QualityAlert:
    def __init__(
        self,
        feature_name: str,
        check: str,
        severity: str,
        message: str,
        value: float | None = None,
    ) -> None:
        self.feature_name = feature_name
        self.check = check
        self.severity = severity
        self.message = message
        self.value = value

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature_name": self.feature_name,
            "check": self.check,
            "severity": self.severity,
            "message": self.message,
            "value": self.value,
        }


def check_null_rate(
    stats: FeatureStats,
    warning_threshold: float = 0.05,
    critical_threshold: float = 0.20,
) -> QualityAlert | None:
    if stats.null_pct >= critical_threshold:
        return QualityAlert(
            feature_name=stats.feature_name,
            check="null_rate",
            severity="critical",
            message=f"Null rate {stats.null_pct:.1%} exceeds {critical_threshold:.0%}",
            value=stats.null_pct,
        )
    if stats.null_pct >= warning_threshold:
        return QualityAlert(
            feature_name=stats.feature_name,
            check="null_rate",
            severity="warning",
            message=f"Null rate {stats.null_pct:.1%} exceeds {warning_threshold:.0%}",
            value=stats.null_pct,
        )
    return None


def check_out_of_range(
    stats: FeatureStats,
    expected_min: float | None = None,
    expected_max: float | None = None,
) -> QualityAlert | None:
    if expected_min is not None and stats.min is not None and stats.min < expected_min:
        return QualityAlert(
            feature_name=stats.feature_name,
            check="out_of_range",
            severity="warning",
            message=f"Min value {stats.min} below expected {expected_min}",
            value=stats.min,
        )
    if expected_max is not None and stats.max is not None and stats.max > expected_max:
        return QualityAlert(
            feature_name=stats.feature_name,
            check="out_of_range",
            severity="warning",
            message=f"Max value {stats.max} above expected {expected_max}",
            value=stats.max,
        )
    return None


def check_cardinality_change(
    current_stats: FeatureStats,
    reference_stats: FeatureStats,
    change_threshold: float = 0.5,
) -> QualityAlert | None:
    if current_stats.unique_count is None or reference_stats.unique_count is None:
        return None
    if reference_stats.unique_count == 0:
        return None

    change = abs(current_stats.unique_count - reference_stats.unique_count) / max(
        reference_stats.unique_count, 1
    )
    if change >= change_threshold:
        return QualityAlert(
            feature_name=current_stats.feature_name,
            check="cardinality_change",
            severity="warning",
            message=(
                f"Cardinality changed by {change:.0%}: "
                f"{reference_stats.unique_count} -> {current_stats.unique_count}"
            ),
            value=change,
        )
    return None


def compute_feature_stats(
    feature_name: str,
    values: list[Any],
    window_start: datetime,
    window_end: datetime,
) -> FeatureStats:
    """Compute statistics for a list of feature values."""
    total = len(values)
    nulls = sum(1 for v in values if v is None)
    non_null = [v for v in values if v is not None]

    stats = FeatureStats(
        feature_name=feature_name,
        window_start=window_start,
        window_end=window_end,
        count=total,
        null_count=nulls,
        null_pct=nulls / max(total, 1),
    )

    # Numeric stats
    numeric = [float(v) for v in non_null if _is_numeric(v)]
    if numeric:
        arr = np.array(numeric)
        stats.mean = float(np.mean(arr))
        stats.stddev = float(np.std(arr))
        stats.min = float(np.min(arr))
        stats.max = float(np.max(arr))
        stats.p25 = float(np.percentile(arr, 25))
        stats.p50 = float(np.percentile(arr, 50))
        stats.p75 = float(np.percentile(arr, 75))
        stats.p95 = float(np.percentile(arr, 95))

    # Unique count and distribution
    str_values = [str(v) for v in non_null]
    stats.unique_count = len(set(str_values))
    dist: dict[str, int] = {}
    for sv in str_values:
        dist[sv] = dist.get(sv, 0) + 1
    stats.value_distribution = dict(sorted(dist.items(), key=lambda x: -x[1])[:100])

    return stats


def _is_numeric(v: Any) -> bool:
    try:
        float(v)
        return True
    except (ValueError, TypeError):
        return False
