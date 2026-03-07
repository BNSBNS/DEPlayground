"""Tests for the event processing pipeline."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.detection.correlation import CorrelationMatch, CorrelationRule
from src.detection.rule_engine import RuleMatch
from src.detection.sigma_loader import SigmaCondition, SigmaDetection, SigmaRule
from src.ingestion.normalizer import NormalizedEvent
from src.pipeline.processor import DetectionAlert, EventProcessor

# --- Fixtures ---


@pytest.fixture()
def sample_event() -> NormalizedEvent:
    return NormalizedEvent(
        event_id="evt-001",
        timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
        source="auth",
        event_type="login_failure",
        severity="warning",
        src_ip="10.0.0.1",
        user="admin",
        action="login",
    )


@pytest.fixture()
def sigma_rule() -> SigmaRule:
    return SigmaRule(
        id="test-rule-001",
        title="Test Brute Force",
        level="high",
        tags=["attack.t1110"],
        mitre_technique_ids=["T1110"],
        detection=SigmaDetection(
            selections={
                "selection": [
                    SigmaCondition(field="event_type", modifier="equals", value="login_failure"),
                ]
            },
            condition="selection",
        ),
    )


@pytest.fixture()
def processor() -> EventProcessor:
    """Processor with no rules (for direct event processing)."""
    return EventProcessor(correlation_rules=[])


@pytest.fixture()
def processor_with_rules(sigma_rule: SigmaRule) -> EventProcessor:
    """Processor with a single sigma rule."""
    proc = EventProcessor(correlation_rules=[])
    proc.rule_engine.add_rule(sigma_rule)
    return proc


# --- DetectionAlert ---


class TestDetectionAlert:
    def test_rule_alert_to_dict(self, sample_event: NormalizedEvent, sigma_rule: SigmaRule) -> None:
        match = RuleMatch(
            rule=sigma_rule, event=sample_event, matched_fields={"event_type": "login_failure"}
        )
        alert = DetectionAlert(alert_type="rule", event=sample_event, rule_match=match)
        d = alert.to_dict()

        assert d["alert_type"] == "rule"
        assert d["event_id"] == "evt-001"
        assert d["rule_id"] == "test-rule-001"
        assert d["rule_title"] == "Test Brute Force"
        assert d["rule_severity"] == "high"

    def test_correlation_alert_to_dict(self, sample_event: NormalizedEvent) -> None:
        corr = CorrelationMatch(
            rule_id="corr-001",
            rule_title="Test Correlation",
            severity="critical",
            mitre_technique_id="T1110",
            group_key="10.0.0.1",
            event_count=5,
            first_event_time=datetime(2024, 1, 1, 11, 50, 0, tzinfo=UTC),
            last_event_time=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
        )
        alert = DetectionAlert(alert_type="correlation", event=sample_event, correlation=corr)
        d = alert.to_dict()

        assert d["alert_type"] == "correlation"
        assert d["correlation_rule_id"] == "corr-001"
        assert d["event_count"] == 5

    def test_plain_alert_to_dict(self, sample_event: NormalizedEvent) -> None:
        alert = DetectionAlert(alert_type="manual", event=sample_event)
        d = alert.to_dict()

        assert d["alert_type"] == "manual"
        assert "rule_id" not in d
        assert "correlation_rule_id" not in d


# --- EventProcessor ---


class TestEventProcessor:
    def test_init_no_rules(self) -> None:
        proc = EventProcessor(correlation_rules=[])
        assert proc.stats == {"processed": 0, "parse_errors": 0, "alerts": 0}
        assert proc.rule_engine.rules == []

    def test_init_loads_sigma_rules_from_dir(self) -> None:
        rules_dir = Path(__file__).resolve().parents[2] / "rules"
        if rules_dir.exists():
            proc = EventProcessor(rules_dir=rules_dir, correlation_rules=[])
            assert len(proc.rule_engine.rules) > 0

    def test_init_default_correlation_rules(self) -> None:
        proc = EventProcessor()
        assert len(proc.correlation_engine.rules) == 3  # BUILTIN_RULES

    def test_process_event_no_match(self, processor: EventProcessor) -> None:
        event = NormalizedEvent(
            timestamp=datetime.now(UTC),
            source="test",
            event_type="normal_event",
        )
        alerts = processor.process_event(event)
        assert alerts == []
        assert processor.stats["processed"] == 1
        assert processor.stats["alerts"] == 0

    def test_process_event_sigma_match(
        self, processor_with_rules: EventProcessor, sample_event: NormalizedEvent
    ) -> None:
        alerts = processor_with_rules.process_event(sample_event)
        assert len(alerts) == 1
        assert alerts[0].alert_type == "rule"
        assert alerts[0].rule_match is not None
        assert processor_with_rules.stats["alerts"] == 1

    def test_process_log_line_json(self, processor: EventProcessor) -> None:
        log_line = json.dumps(
            {
                "event_id": "evt-json-001",
                "timestamp": "2024-01-01T12:00:00+00:00",
                "source": "auth",
                "event_type": "login_success",
                "severity": "info",
                "src_ip": "10.0.0.1",
                "user": "user1",
            }
        )
        alerts = processor.process_log_line(log_line)
        assert isinstance(alerts, list)
        assert processor.stats["processed"] == 1
        assert processor.stats["parse_errors"] == 0

    def test_process_log_line_parse_error(self, processor: EventProcessor) -> None:
        alerts = processor.process_log_line("this is not a valid log line at all")
        assert alerts == []
        assert processor.stats["parse_errors"] == 1

    def test_stats_accumulate(self, processor: EventProcessor) -> None:
        event = NormalizedEvent(timestamp=datetime.now(UTC), source="test", event_type="test")
        processor.process_event(event)
        processor.process_event(event)
        processor.process_event(event)
        assert processor.stats["processed"] == 3


class TestProcessorCorrelation:
    def test_threshold_correlation(self) -> None:
        rule = CorrelationRule(
            id="test-corr-001",
            title="Test Threshold",
            severity="high",
            rule_type="threshold",
            threshold_count=3,
            window_seconds=600,
            group_by="src_ip",
            event_filter={"event_type": "login_failure"},
        )
        proc = EventProcessor(correlation_rules=[rule])

        all_alerts: list[DetectionAlert] = []
        for i in range(5):
            event = NormalizedEvent(
                event_id=f"evt-{i}",
                timestamp=datetime(2024, 1, 1, 12, i, 0, tzinfo=UTC),
                source="auth",
                event_type="login_failure",
                src_ip="10.0.0.1",
            )
            all_alerts.extend(proc.process_event(event))

        corr_alerts = [a for a in all_alerts if a.alert_type == "correlation"]
        assert len(corr_alerts) == 1
        assert corr_alerts[0].correlation is not None
        assert corr_alerts[0].correlation.rule_id == "test-corr-001"
