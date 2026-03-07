"""Tests for SQLite event and alert storage."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from src.detection.correlation import CorrelationMatch
from src.detection.rule_engine import RuleMatch
from src.detection.sigma_loader import SigmaCondition, SigmaDetection, SigmaRule
from src.ingestion.normalizer import NormalizedEvent
from src.pipeline.processor import DetectionAlert
from src.storage.event_store import EventStore


@pytest.fixture()
def store() -> EventStore:
    """In-memory SQLite store."""
    return EventStore(":memory:")


@pytest.fixture()
def sample_event() -> NormalizedEvent:
    return NormalizedEvent(
        event_id="evt-store-001",
        timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
        source="auth",
        event_type="login_failure",
        severity="warning",
        src_ip="10.0.0.1",
        user="admin",
        action="login",
        hostname="server-01",
        details={"reason": "bad_password"},
    )


@pytest.fixture()
def sample_rule_alert(sample_event: NormalizedEvent) -> DetectionAlert:
    rule = SigmaRule(
        id="sigma-test-001",
        title="Test Rule",
        level="high",
        detection=SigmaDetection(
            selections={
                "selection": [
                    SigmaCondition(field="event_type", modifier="equals", value="login_failure"),
                ]
            },
            condition="selection",
        ),
    )
    match = RuleMatch(rule=rule, event=sample_event, matched_fields={"event_type": "login_failure"})
    return DetectionAlert(alert_type="rule", event=sample_event, rule_match=match)


@pytest.fixture()
def sample_corr_alert(sample_event: NormalizedEvent) -> DetectionAlert:
    corr = CorrelationMatch(
        rule_id="corr-test-001",
        rule_title="Test Correlation",
        severity="critical",
        mitre_technique_id="T1110",
        group_key="10.0.0.1",
        event_count=5,
        first_event_time=datetime(2024, 1, 1, 11, 50, 0, tzinfo=UTC),
        last_event_time=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
    )
    return DetectionAlert(alert_type="correlation", event=sample_event, correlation=corr)


# --- Event Storage ---


class TestEventStorage:
    def test_store_and_query_event(self, store: EventStore, sample_event: NormalizedEvent) -> None:
        store.store_event(sample_event)
        results = store.query_events()
        assert len(results) == 1
        assert results[0]["event_id"] == "evt-store-001"
        assert results[0]["source"] == "auth"

    def test_query_by_src_ip(self, store: EventStore, sample_event: NormalizedEvent) -> None:
        store.store_event(sample_event)
        results = store.query_events(src_ip="10.0.0.1")
        assert len(results) == 1

        results = store.query_events(src_ip="192.168.1.1")
        assert len(results) == 0

    def test_query_by_user(self, store: EventStore, sample_event: NormalizedEvent) -> None:
        store.store_event(sample_event)
        results = store.query_events(user="admin")
        assert len(results) == 1

    def test_query_by_event_type(self, store: EventStore, sample_event: NormalizedEvent) -> None:
        store.store_event(sample_event)
        results = store.query_events(event_type="login_failure")
        assert len(results) == 1

    def test_query_with_limit_offset(self, store: EventStore) -> None:
        for i in range(10):
            event = NormalizedEvent(
                event_id=f"evt-{i:03d}",
                timestamp=datetime(2024, 1, 1, 12, i, 0, tzinfo=UTC),
                source="auth",
                event_type="login",
            )
            store.store_event(event)

        results = store.query_events(limit=3)
        assert len(results) == 3

        results = store.query_events(limit=3, offset=8)
        assert len(results) == 2

    def test_duplicate_event_ignored(
        self, store: EventStore, sample_event: NormalizedEvent
    ) -> None:
        store.store_event(sample_event)
        store.store_event(sample_event)  # Same event_id
        results = store.query_events()
        assert len(results) == 1

    def test_event_details_stored_as_json(
        self, store: EventStore, sample_event: NormalizedEvent
    ) -> None:
        store.store_event(sample_event)
        results = store.query_events()
        details = json.loads(results[0]["details"])
        assert details["reason"] == "bad_password"


# --- Alert Storage ---


class TestAlertStorage:
    def test_store_and_query_rule_alert(
        self, store: EventStore, sample_event: NormalizedEvent, sample_rule_alert: DetectionAlert
    ) -> None:
        store.store_event(sample_event)
        store.store_alert(sample_rule_alert)
        results = store.query_alerts()
        assert len(results) == 1
        assert results[0]["alert_type"] == "rule"
        assert results[0]["rule_id"] == "sigma-test-001"

    def test_store_correlation_alert(
        self, store: EventStore, sample_event: NormalizedEvent, sample_corr_alert: DetectionAlert
    ) -> None:
        store.store_event(sample_event)
        store.store_alert(sample_corr_alert)
        results = store.query_alerts()
        assert len(results) == 1
        assert results[0]["alert_type"] == "correlation"
        assert results[0]["rule_id"] == "corr-test-001"

    def test_query_alerts_by_severity(
        self, store: EventStore, sample_event: NormalizedEvent, sample_rule_alert: DetectionAlert
    ) -> None:
        store.store_event(sample_event)
        store.store_alert(sample_rule_alert)

        results = store.query_alerts(severity="high")
        assert len(results) == 1

        results = store.query_alerts(severity="low")
        assert len(results) == 0

    def test_query_alerts_by_rule_id(
        self, store: EventStore, sample_event: NormalizedEvent, sample_rule_alert: DetectionAlert
    ) -> None:
        store.store_event(sample_event)
        store.store_alert(sample_rule_alert)

        results = store.query_alerts(rule_id="sigma-test-001")
        assert len(results) == 1

        results = store.query_alerts(rule_id="nonexistent")
        assert len(results) == 0


# --- Stats ---


class TestStats:
    def test_empty_stats(self, store: EventStore) -> None:
        stats = store.get_stats()
        assert stats == {"event_count": 0, "alert_count": 0}

    def test_stats_after_inserts(
        self, store: EventStore, sample_event: NormalizedEvent, sample_rule_alert: DetectionAlert
    ) -> None:
        store.store_event(sample_event)
        store.store_alert(sample_rule_alert)
        stats = store.get_stats()
        assert stats["event_count"] == 1
        assert stats["alert_count"] == 1

    def test_close(self, store: EventStore) -> None:
        store.close()
        # Should not raise — but subsequent queries will fail
