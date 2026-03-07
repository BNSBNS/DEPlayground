"""Tests for event normalization (Phase 2)."""

from __future__ import annotations

from datetime import UTC, datetime

from src.ingestion.normalizer import NormalizedEvent, normalize_from_log_event


class TestNormalizedEvent:
    """NormalizedEvent model tests."""

    def test_creates_with_defaults(self) -> None:
        event = NormalizedEvent(
            timestamp=datetime(2024, 6, 1, tzinfo=UTC),
            source="auth",
            event_type="login_success",
        )
        assert event.event_id  # UUID auto-generated
        assert event.severity == "info"
        assert event.details == {}

    def test_all_fields(self) -> None:
        event = NormalizedEvent(
            timestamp=datetime(2024, 6, 1, tzinfo=UTC),
            source="firewall",
            event_type="connection_blocked",
            severity="warning",
            src_ip="10.0.0.1",
            dst_ip="192.168.1.1",
            src_port=12345,
            dst_port=443,
            user="admin",
            action="deny",
            protocol="tcp",
            hostname="fw-01",
            details={"bytes_sent": 1024},
            raw="original log line",
        )
        assert event.src_port == 12345
        assert event.protocol == "tcp"
        assert event.raw == "original log line"


class TestNormalizeFromLogEvent:
    """normalize_from_log_event tests."""

    def test_normalizes_auth_event(self) -> None:
        event_dict = {
            "event_id": "abc-123",
            "timestamp": datetime(2024, 6, 1, 12, 0, 0, tzinfo=UTC),
            "source": "auth",
            "event_type": "login_success",
            "severity": "info",
            "src_ip": "10.0.0.1",
            "dst_ip": "10.0.0.2",
            "user": "admin",
            "action": "allow",
            "details": {"method": "sso", "host": "webserver"},
        }
        result = normalize_from_log_event(event_dict)
        assert isinstance(result, NormalizedEvent)
        assert result.event_id == "abc-123"
        assert result.source == "auth"
        assert result.user == "admin"
        assert result.hostname == "webserver"

    def test_normalizes_firewall_event(self) -> None:
        event_dict = {
            "timestamp": datetime(2024, 6, 1, tzinfo=UTC),
            "source": "firewall",
            "event_type": "connection_allowed",
            "src_ip": "10.0.0.1",
            "dst_ip": "203.0.113.50",
            "action": "allow",
            "details": {"dst_port": 443, "protocol": "tcp"},
        }
        result = normalize_from_log_event(event_dict)
        assert result.dst_port == 443
        assert result.protocol == "tcp"

    def test_handles_missing_fields(self) -> None:
        event_dict = {
            "timestamp": datetime(2024, 6, 1, tzinfo=UTC),
            "source": "dns",
            "event_type": "dns_query",
        }
        result = normalize_from_log_event(event_dict)
        assert result.src_ip is None
        assert result.user is None
        assert result.action is None

    def test_handles_string_timestamp(self) -> None:
        event_dict = {
            "timestamp": "2024-06-01T12:00:00+00:00",
            "source": "app",
            "event_type": "http_request",
        }
        result = normalize_from_log_event(event_dict)
        assert result.timestamp.tzinfo is not None

    def test_handles_naive_timestamp(self) -> None:
        event_dict = {
            "timestamp": "2024-06-01T12:00:00",
            "source": "app",
            "event_type": "http_request",
        }
        result = normalize_from_log_event(event_dict)
        assert result.timestamp.tzinfo == UTC

    def test_preserves_details(self) -> None:
        details = {"custom_field": "value", "nested": {"a": 1}}
        event_dict = {
            "timestamp": datetime(2024, 6, 1, tzinfo=UTC),
            "source": "app",
            "event_type": "custom",
            "details": details,
        }
        result = normalize_from_log_event(event_dict)
        assert result.details["custom_field"] == "value"
        assert result.details["nested"]["a"] == 1
