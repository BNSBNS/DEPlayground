"""Event processing pipeline.

Orchestrates: parse → normalize → rule match → correlate → emit alerts.
Can be driven by Kafka (Phase 5) or called directly for batch/testing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.detection.correlation import BUILTIN_RULES, CorrelationEngine, CorrelationRule
from src.detection.rule_engine import RuleEngine
from src.detection.sigma_loader import load_rules_from_directory
from src.ingestion.log_parser import ParseError, parse_log_line
from src.ingestion.normalizer import NormalizedEvent, normalize_from_log_event

if TYPE_CHECKING:
    from pathlib import Path

    from src.detection.correlation import CorrelationMatch
    from src.detection.rule_engine import RuleMatch


class DetectionAlert:
    """Alert produced by the detection pipeline."""

    __slots__ = ("alert_type", "correlation", "event", "rule_match")

    def __init__(
        self,
        alert_type: str,
        event: NormalizedEvent,
        rule_match: RuleMatch | None = None,
        correlation: CorrelationMatch | None = None,
    ) -> None:
        self.alert_type = alert_type
        self.event = event
        self.rule_match = rule_match
        self.correlation = correlation

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for storage."""
        result: dict[str, Any] = {
            "alert_type": self.alert_type,
            "event_id": self.event.event_id,
            "timestamp": self.event.timestamp.isoformat(),
            "event_type": self.event.event_type,
            "severity": self.event.severity,
            "src_ip": self.event.src_ip,
            "user": self.event.user,
        }
        if self.rule_match:
            result["rule_id"] = self.rule_match.rule.id
            result["rule_title"] = self.rule_match.rule.title
            result["rule_severity"] = self.rule_match.rule.severity
        if self.correlation:
            result["correlation_rule_id"] = self.correlation.rule_id
            result["correlation_title"] = self.correlation.rule_title
            result["correlation_severity"] = self.correlation.severity
            result["event_count"] = self.correlation.event_count
        return result


class EventProcessor:
    """Pipeline that processes log lines through detection and correlation."""

    def __init__(
        self,
        rules_dir: Path | None = None,
        correlation_rules: list[CorrelationRule] | None = None,
    ) -> None:
        self._rule_engine = RuleEngine()
        self._correlation_engine = CorrelationEngine(correlation_rules or list(BUILTIN_RULES))
        self._stats = {"processed": 0, "parse_errors": 0, "alerts": 0}

        if rules_dir and rules_dir.exists():
            for rule in load_rules_from_directory(rules_dir):
                self._rule_engine.add_rule(rule)

    @property
    def stats(self) -> dict[str, int]:
        """Processing statistics."""
        return dict(self._stats)

    @property
    def rule_engine(self) -> RuleEngine:
        """Access to the rule engine."""
        return self._rule_engine

    @property
    def correlation_engine(self) -> CorrelationEngine:
        """Access to the correlation engine."""
        return self._correlation_engine

    def process_log_line(self, line: str) -> list[DetectionAlert]:
        """Process a single log line through the full pipeline."""
        self._stats["processed"] += 1
        try:
            parsed = parse_log_line(line)
        except ParseError:
            self._stats["parse_errors"] += 1
            return []

        event = normalize_from_log_event(parsed)
        return self._detect(event)

    def process_event(self, event: NormalizedEvent) -> list[DetectionAlert]:
        """Process a pre-normalized event through detection + correlation."""
        self._stats["processed"] += 1
        return self._detect(event)

    def _detect(self, event: NormalizedEvent) -> list[DetectionAlert]:
        """Run detection and correlation on a normalized event."""
        alerts: list[DetectionAlert] = []

        # Sigma rule matching
        for match in self._rule_engine.match(event):
            alerts.append(DetectionAlert(alert_type="rule", event=event, rule_match=match))

        # Correlation
        for corr_match in self._correlation_engine.process_event(event):
            alerts.append(
                DetectionAlert(alert_type="correlation", event=event, correlation=corr_match)
            )

        self._stats["alerts"] += len(alerts)
        return alerts
