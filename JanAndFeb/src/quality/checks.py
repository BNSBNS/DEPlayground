"""Data quality checks for trade events.

This module implements quality checks inspired by Great Expectations but
simplified for a learning platform. Each check returns a score (0-1) and
details about any issues found.

Quality Dimensions (based on DAMA data quality framework):
1. Completeness - Are all required fields present?
2. Validity - Are values within acceptable ranges?
3. Timeliness - Is data fresh enough?
4. Uniqueness - Are there duplicates?
5. Consistency - Are values internally consistent?
6. Accuracy - Do values match reality? (hard to verify without reference)
"""

import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import structlog

from src.common.models import TradeEvent
from src.quality import metrics

logger = structlog.get_logger(__name__)


@dataclass
class QualityIssue:
    """A single quality issue found during validation."""

    check_name: str
    field: str
    issue: str
    severity: str  # "error", "warning", "info"
    value: Any = None


@dataclass
class QualityReport:
    """Report from quality checks on a record.

    Attributes:
        is_valid: True if record passes all required checks
        score: Overall quality score (0-1)
        issues: List of quality issues found
        checks_performed: Names of checks that were run
        duration_ms: Time taken for all checks in milliseconds
    """

    is_valid: bool
    score: float
    issues: list[QualityIssue] = field(default_factory=list)
    checks_performed: list[str] = field(default_factory=list)
    duration_ms: float = 0.0

    @property
    def has_errors(self) -> bool:
        """Check if any error-level issues exist."""
        return any(i.severity == "error" for i in self.issues)

    @property
    def has_warnings(self) -> bool:
        """Check if any warning-level issues exist."""
        return any(i.severity == "warning" for i in self.issues)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "is_valid": self.is_valid,
            "score": self.score,
            "issues": [
                {
                    "check": i.check_name,
                    "field": i.field,
                    "issue": i.issue,
                    "severity": i.severity,
                }
                for i in self.issues
            ],
            "checks_performed": self.checks_performed,
            "duration_ms": self.duration_ms,
        }


class QualityChecker:
    """Performs data quality checks on trade events.

    The checker runs multiple quality checks and aggregates the results
    into a single QualityReport with an overall score.

    Example:
        >>> checker = QualityChecker(source="finnhub")
        >>> trade = TradeEvent(...)
        >>> report = checker.check(trade)
        >>> if report.is_valid:
        ...     process(trade)
        ... else:
        ...     send_to_dlq(trade, report)
    """

    def __init__(
        self,
        source: str = "unknown",
        max_price: Decimal = Decimal("1000000"),
        max_volume: Decimal = Decimal("10000000"),
        max_age_seconds: int = 300,
        valid_symbols_pattern: str = r"^[A-Z0-9_:]+$",
    ):
        """Initialize the quality checker.

        Args:
            source: Data source name (for metrics labeling)
            max_price: Maximum acceptable price
            max_volume: Maximum acceptable volume
            max_age_seconds: Maximum age of events in seconds
            valid_symbols_pattern: Regex pattern for valid symbols
        """
        self.source = source
        self.max_price = max_price
        self.max_volume = max_volume
        self.max_age_seconds = max_age_seconds
        self.valid_symbols_pattern = valid_symbols_pattern

        # Track seen trade IDs for duplicate detection (LRU-style)
        self._seen_ids: dict[str, datetime] = {}
        self._max_seen_ids = 100000

    def check(self, trade: TradeEvent) -> QualityReport:
        """Run all quality checks on a trade event.

        Args:
            trade: Trade event to validate

        Returns:
            QualityReport with overall score and any issues
        """
        start_time = time.perf_counter()
        issues: list[QualityIssue] = []
        checks_performed: list[str] = []

        # Run each check
        issues.extend(self._check_completeness(trade))
        checks_performed.append("completeness")

        issues.extend(self._check_validity(trade))
        checks_performed.append("validity")

        issues.extend(self._check_timeliness(trade))
        checks_performed.append("timeliness")

        issues.extend(self._check_uniqueness(trade))
        checks_performed.append("uniqueness")

        issues.extend(self._check_consistency(trade))
        checks_performed.append("consistency")

        # Calculate overall score
        # Weight: errors=-0.5, warnings=-0.1, info=-0.01
        score = 1.0
        for issue in issues:
            if issue.severity == "error":
                score -= 0.5
            elif issue.severity == "warning":
                score -= 0.1
            else:
                score -= 0.01
        score = max(0.0, score)

        # Determine validity (any errors = invalid)
        is_valid = not any(i.severity == "error" for i in issues)

        duration_ms = (time.perf_counter() - start_time) * 1000

        report = QualityReport(
            is_valid=is_valid,
            score=score,
            issues=issues,
            checks_performed=checks_performed,
            duration_ms=duration_ms,
        )

        # Record metrics
        metrics.record_quality_check(
            source=self.source,
            check_type="overall",
            score=score,
            duration_seconds=duration_ms / 1000,
        )

        if not is_valid:
            for issue in issues:
                if issue.severity == "error":
                    metrics.record_validation_failure(
                        source=self.source,
                        failure_type=issue.check_name,
                        symbol=trade.symbol,
                    )
        else:
            metrics.record_valid_record(self.source)

        return report

    def _check_completeness(self, trade: TradeEvent) -> list[QualityIssue]:
        """Check that all required fields are present and non-null.

        Completeness Score: (non-null fields) / (total required fields)
        """
        issues = []
        required_fields = [
            "trade_id",
            "symbol",
            "price",
            "volume",
            "side",
            "event_timestamp",
        ]

        for field_name in required_fields:
            value = getattr(trade, field_name, None)
            if value is None:
                issues.append(
                    QualityIssue(
                        check_name="completeness",
                        field=field_name,
                        issue=f"Required field '{field_name}' is null",
                        severity="error",
                    )
                )

        # trader_id is optional but good to have
        if not trade.trader_id:
            issues.append(
                QualityIssue(
                    check_name="completeness",
                    field="trader_id",
                    issue="trader_id is empty",
                    severity="warning",
                )
            )

        # Record completeness metric
        filled = sum(1 for f in required_fields if getattr(trade, f, None) is not None)
        ratio = filled / len(required_fields)
        metrics.record_completeness(self.source, trade.symbol, ratio)

        return issues

    def _check_validity(self, trade: TradeEvent) -> list[QualityIssue]:
        """Check that values are within acceptable ranges."""
        issues = []

        # Price validation
        if trade.price < 0:
            issues.append(
                QualityIssue(
                    check_name="validity_price",
                    field="price",
                    issue=f"Price is negative: {trade.price}",
                    severity="error",
                    value=trade.price,
                )
            )
            metrics.record_schema_violation(self.source, "price", "negative")
        elif trade.price > self.max_price:
            issues.append(
                QualityIssue(
                    check_name="validity_price",
                    field="price",
                    issue=f"Price exceeds maximum: {trade.price} > {self.max_price}",
                    severity="warning",
                    value=trade.price,
                )
            )
            metrics.record_schema_violation(self.source, "price", "out_of_range")

        # Volume validation
        if trade.volume <= 0:
            issues.append(
                QualityIssue(
                    check_name="validity_volume",
                    field="volume",
                    issue=f"Volume must be positive: {trade.volume}",
                    severity="error",
                    value=trade.volume,
                )
            )
            metrics.record_schema_violation(self.source, "volume", "non_positive")
        elif trade.volume > self.max_volume:
            issues.append(
                QualityIssue(
                    check_name="validity_volume",
                    field="volume",
                    issue=f"Volume exceeds maximum: {trade.volume} > {self.max_volume}",
                    severity="warning",
                    value=trade.volume,
                )
            )

        # Symbol validation
        import re

        if not re.match(self.valid_symbols_pattern, trade.symbol):
            issues.append(
                QualityIssue(
                    check_name="validity_symbol",
                    field="symbol",
                    issue=f"Symbol doesn't match pattern: {trade.symbol}",
                    severity="error",
                    value=trade.symbol,
                )
            )
            metrics.record_schema_violation(self.source, "symbol", "invalid_format")

        return issues

    def _check_timeliness(self, trade: TradeEvent) -> list[QualityIssue]:
        """Check that event timestamp is recent enough."""
        issues = []
        now = datetime.now(UTC)

        # Ensure timestamp is timezone-aware
        event_time = trade.event_timestamp
        if event_time.tzinfo is None:
            event_time = event_time.replace(tzinfo=UTC)

        age_seconds = (now - event_time).total_seconds()

        # Record freshness
        metrics.record_freshness(self.source, trade.symbol, age_seconds)

        # Check for future timestamps (clock skew)
        if age_seconds < -60:  # More than 1 minute in future
            issues.append(
                QualityIssue(
                    check_name="timeliness",
                    field="event_timestamp",
                    issue=f"Timestamp is in the future by {abs(age_seconds):.0f}s",
                    severity="warning",
                    value=event_time.isoformat(),
                )
            )

        # Check for stale data
        if age_seconds > self.max_age_seconds:
            issues.append(
                QualityIssue(
                    check_name="timeliness",
                    field="event_timestamp",
                    issue=f"Event is too old: {age_seconds:.0f}s > {self.max_age_seconds}s",
                    severity="warning",
                    value=event_time.isoformat(),
                )
            )

        # Check for very old data (likely wrong)
        if age_seconds > 86400:  # More than 1 day
            issues.append(
                QualityIssue(
                    check_name="timeliness",
                    field="event_timestamp",
                    issue=f"Event is more than 1 day old: {age_seconds / 3600:.1f} hours",
                    severity="error",
                    value=event_time.isoformat(),
                )
            )

        return issues

    def _check_uniqueness(self, trade: TradeEvent) -> list[QualityIssue]:
        """Check for duplicate trade IDs."""
        issues = []
        trade_id_str = str(trade.trade_id)

        if trade_id_str in self._seen_ids:
            first_seen = self._seen_ids[trade_id_str]
            issues.append(
                QualityIssue(
                    check_name="uniqueness",
                    field="trade_id",
                    issue=f"Duplicate trade_id, first seen at {first_seen.isoformat()}",
                    severity="warning",
                    value=trade_id_str,
                )
            )
            metrics.record_duplicate(self.source, trade.symbol)
        else:
            # Add to seen IDs (with LRU eviction if needed)
            if len(self._seen_ids) >= self._max_seen_ids:
                # Remove oldest 10%
                oldest_keys = sorted(self._seen_ids.keys(), key=lambda k: self._seen_ids[k])[
                    : self._max_seen_ids // 10
                ]
                for key in oldest_keys:
                    del self._seen_ids[key]

            self._seen_ids[trade_id_str] = datetime.now(UTC)

        return issues

    def _check_consistency(self, trade: TradeEvent) -> list[QualityIssue]:
        """Check internal consistency of the record."""
        issues = []

        # Zero price with non-zero volume is suspicious
        if trade.price == Decimal("0") and trade.volume > Decimal("0"):
            issues.append(
                QualityIssue(
                    check_name="consistency",
                    field="price",
                    issue="Zero price with non-zero volume",
                    severity="warning",
                )
            )

        # Very small trades might be errors
        notional = trade.price * trade.volume
        if Decimal("0") < notional < Decimal("0.01"):
            issues.append(
                QualityIssue(
                    check_name="consistency",
                    field="notional",
                    issue=f"Very small notional value: {notional}",
                    severity="info",
                )
            )

        return issues
