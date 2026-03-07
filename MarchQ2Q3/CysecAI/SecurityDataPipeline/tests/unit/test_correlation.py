"""Tests for multi-event correlation engine (Phase 4)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from src.detection.correlation import (
    BUILTIN_RULES,
    CorrelationEngine,
    CorrelationRule,
)
from src.ingestion.normalizer import NormalizedEvent


def _make_event(
    event_type: str = "test",
    src_ip: str = "10.0.0.1",
    user: str | None = None,
    timestamp: datetime | None = None,
    action: str | None = None,
    **details: object,
) -> NormalizedEvent:
    """Create a NormalizedEvent for testing."""
    return NormalizedEvent(
        timestamp=timestamp or datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC),
        source="test",
        event_type=event_type,
        src_ip=src_ip,
        user=user,
        action=action,
        details=dict(details),
    )


class TestThresholdCorrelation:
    """Threshold-based correlation tests."""

    def _threshold_rule(self, count: int = 5, window: int = 600) -> CorrelationRule:
        return CorrelationRule(
            id="test-threshold",
            title="Test Threshold",
            severity="high",
            rule_type="threshold",
            threshold_count=count,
            window_seconds=window,
            event_filter={"event_type": "login_failure"},
            group_by="src_ip",
        )

    def test_fires_at_threshold(self) -> None:
        engine = CorrelationEngine([self._threshold_rule(count=3)])
        base = datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC)
        matches: list[object] = []
        for i in range(3):
            result = engine.process_event(
                _make_event("login_failure", timestamp=base + timedelta(seconds=i * 10))
            )
            matches.extend(result)
        assert len(matches) == 1
        assert matches[0].rule_id == "test-threshold"  # type: ignore[union-attr]

    def test_no_fire_below_threshold(self) -> None:
        engine = CorrelationEngine([self._threshold_rule(count=5)])
        base = datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC)
        for i in range(4):
            matches = engine.process_event(
                _make_event("login_failure", timestamp=base + timedelta(seconds=i * 10))
            )
            assert matches == []

    def test_groups_by_ip(self) -> None:
        engine = CorrelationEngine([self._threshold_rule(count=2)])
        base = datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC)
        # 2 events from different IPs — should not fire
        engine.process_event(_make_event("login_failure", src_ip="10.0.0.1", timestamp=base))
        matches = engine.process_event(
            _make_event("login_failure", src_ip="10.0.0.2", timestamp=base + timedelta(seconds=5))
        )
        assert matches == []

    def test_window_expiry(self) -> None:
        engine = CorrelationEngine([self._threshold_rule(count=2, window=60)])
        base = datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC)
        # First event
        engine.process_event(_make_event("login_failure", timestamp=base))
        # Second event after window expires
        matches = engine.process_event(
            _make_event("login_failure", timestamp=base + timedelta(seconds=120))
        )
        assert matches == []

    def test_ignores_non_matching_events(self) -> None:
        engine = CorrelationEngine([self._threshold_rule(count=2)])
        base = datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC)
        engine.process_event(_make_event("login_success", timestamp=base))
        matches = engine.process_event(
            _make_event("login_success", timestamp=base + timedelta(seconds=5))
        )
        assert matches == []

    def test_fires_only_once_per_group(self) -> None:
        engine = CorrelationEngine([self._threshold_rule(count=2)])
        base = datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC)
        results: list[object] = []
        for i in range(5):
            matches = engine.process_event(
                _make_event("login_failure", timestamp=base + timedelta(seconds=i * 10))
            )
            results.extend(matches)
        # Should fire exactly once
        assert len(results) == 1


class TestSequenceCorrelation:
    """Sequence-based correlation tests (event_a → event_b)."""

    def _sequence_rule(self, window: int = 600) -> CorrelationRule:
        return CorrelationRule(
            id="test-sequence",
            title="Test Sequence",
            severity="critical",
            rule_type="sequence",
            window_seconds=window,
            group_by="src_ip",
            event_a_filter={"event_type": "login_failure"},
            event_b_filter={"event_type": "login_success"},
        )

    def test_fires_on_a_then_b(self) -> None:
        engine = CorrelationEngine([self._sequence_rule()])
        base = datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC)
        engine.process_event(_make_event("login_failure", timestamp=base))
        matches = engine.process_event(
            _make_event("login_success", timestamp=base + timedelta(seconds=30))
        )
        assert len(matches) == 1
        assert matches[0].rule_id == "test-sequence"

    def test_no_fire_b_without_a(self) -> None:
        engine = CorrelationEngine([self._sequence_rule()])
        base = datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC)
        matches = engine.process_event(_make_event("login_success", timestamp=base))
        assert matches == []

    def test_no_fire_a_without_b(self) -> None:
        engine = CorrelationEngine([self._sequence_rule()])
        base = datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC)
        matches = engine.process_event(_make_event("login_failure", timestamp=base))
        assert matches == []

    def test_window_expiry(self) -> None:
        engine = CorrelationEngine([self._sequence_rule(window=60)])
        base = datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC)
        engine.process_event(_make_event("login_failure", timestamp=base))
        matches = engine.process_event(
            _make_event("login_success", timestamp=base + timedelta(seconds=120))
        )
        assert matches == []

    def test_different_ips_no_fire(self) -> None:
        engine = CorrelationEngine([self._sequence_rule()])
        base = datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC)
        engine.process_event(_make_event("login_failure", src_ip="10.0.0.1", timestamp=base))
        matches = engine.process_event(
            _make_event("login_success", src_ip="10.0.0.2", timestamp=base + timedelta(seconds=30))
        )
        assert matches == []


class TestCorrelationEngine:
    """CorrelationEngine class tests."""

    def test_add_rule(self) -> None:
        engine = CorrelationEngine()
        engine.add_rule(
            CorrelationRule(
                id="r1",
                title="Test",
                rule_type="threshold",
                threshold_count=3,
                event_filter={"event_type": "test"},
            )
        )
        assert len(engine.rules) == 1

    def test_process_events_batch(self) -> None:
        rule = CorrelationRule(
            id="batch-test",
            title="Batch Test",
            severity="high",
            rule_type="threshold",
            threshold_count=3,
            window_seconds=600,
            event_filter={"event_type": "login_failure"},
            group_by="src_ip",
        )
        engine = CorrelationEngine([rule])
        base = datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC)
        events = [
            _make_event("login_failure", timestamp=base + timedelta(seconds=i * 10))
            for i in range(5)
        ]
        matches = engine.process_events(events)
        assert len(matches) == 1

    def test_reset_clears_state(self) -> None:
        rule = CorrelationRule(
            id="reset-test",
            title="Reset Test",
            severity="high",
            rule_type="threshold",
            threshold_count=2,
            window_seconds=600,
            event_filter={"event_type": "login_failure"},
            group_by="src_ip",
        )
        engine = CorrelationEngine([rule])
        base = datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC)
        engine.process_event(_make_event("login_failure", timestamp=base))
        engine.reset()
        # After reset, previous events are gone
        matches = engine.process_event(
            _make_event("login_failure", timestamp=base + timedelta(seconds=5))
        )
        assert matches == []

    def test_builtin_rules_exist(self) -> None:
        assert len(BUILTIN_RULES) >= 3
        ids = {r.id for r in BUILTIN_RULES}
        assert "corr-bf-001" in ids
        assert "corr-lm-001" in ids
        assert "corr-xp-001" in ids

    def test_brute_force_builtin(self) -> None:
        bf_rule = next(r for r in BUILTIN_RULES if r.id == "corr-bf-001")
        engine = CorrelationEngine([bf_rule])
        base = datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC)
        # 3 failures then success
        for i in range(3):
            engine.process_event(
                _make_event("login_failure", timestamp=base + timedelta(seconds=i * 10))
            )
        matches = engine.process_event(
            _make_event("login_success", timestamp=base + timedelta(seconds=60))
        )
        assert len(matches) == 1
        assert matches[0].severity == "critical"

    def test_cross_project_correlation(self) -> None:
        xp_rule = next(r for r in BUILTIN_RULES if r.id == "corr-xp-001")
        engine = CorrelationEngine([xp_rule])
        base = datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC)
        # Two alerts from different projects, same IP
        engine.process_event(
            _make_event(
                "security_alert:FRAUD-001",
                src_ip="203.0.113.50",
                action="alert",
                timestamp=base,
            )
        )
        matches = engine.process_event(
            _make_event(
                "security_alert:NET-001",
                src_ip="203.0.113.50",
                action="alert",
                timestamp=base + timedelta(seconds=60),
            )
        )
        assert len(matches) == 1
        assert matches[0].rule_id == "corr-xp-001"
