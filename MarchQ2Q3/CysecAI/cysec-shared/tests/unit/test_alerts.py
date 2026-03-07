"""Tests for SecurityAlert model and AlertSeverity enum."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

import pytest

from cysec_shared.models.alerts import AlertSeverity, SecurityAlert
from cysec_shared.testing.fixtures import make_security_alert


class TestAlertSeverity:
    """AlertSeverity enum tests."""

    def test_all_levels_defined(self) -> None:
        assert set(AlertSeverity) == {
            AlertSeverity.CRITICAL,
            AlertSeverity.HIGH,
            AlertSeverity.MEDIUM,
            AlertSeverity.LOW,
            AlertSeverity.INFO,
        }

    def test_serializes_as_string(self) -> None:
        assert AlertSeverity.CRITICAL == "critical"
        assert str(AlertSeverity.HIGH) == "high"


class TestSecurityAlert:
    """SecurityAlert model tests."""

    def test_create_with_required_fields(self) -> None:
        alert = SecurityAlert(
            source_project="fraud-detection",
            rule_id="FRAUD-001",
            severity="high",
            title="Suspicious transaction",
            description="Amount 10x above user average.",
            affected_asset="user-123",
        )
        assert alert.source_project == "fraud-detection"
        assert alert.severity == "high"
        assert alert.affected_asset == "user-123"

    def test_auto_generates_uuid(self) -> None:
        alert = make_security_alert()
        uuid.UUID(alert.alert_id)  # raises ValueError if invalid

    def test_auto_generates_timestamp(self) -> None:
        before = datetime.now(UTC)
        alert = make_security_alert()
        after = datetime.now(UTC)
        assert before <= alert.timestamp <= after

    def test_optional_fields_default_to_none(self) -> None:
        alert = SecurityAlert(
            source_project="test",
            rule_id="T-001",
            severity="low",
            title="Test",
            description="Test",
            affected_asset="test",
        )
        assert alert.mitre_technique_id is None
        assert alert.mitre_tactic is None
        assert alert.source_ip is None
        assert alert.dest_ip is None
        assert alert.user is None

    def test_list_fields_default_to_empty(self) -> None:
        alert = SecurityAlert(
            source_project="test",
            rule_id="T-001",
            severity="info",
            title="Test",
            description="Test",
            affected_asset="test",
        )
        assert alert.cia_impact == []
        assert alert.recommendations == []
        assert alert.evidence == {}

    def test_json_round_trip(self) -> None:
        original = make_security_alert(
            source_project="network-monitor",
            severity="critical",
            source_ip="10.0.0.1",
            dest_ip="192.168.1.100",
        )
        json_str = original.model_dump_json()
        restored = SecurityAlert.model_validate_json(json_str)
        assert restored.source_project == original.source_project
        assert restored.alert_id == original.alert_id
        assert restored.severity == original.severity
        assert restored.source_ip == original.source_ip

    def test_json_output_is_valid_json(self) -> None:
        alert = make_security_alert()
        parsed = json.loads(alert.model_dump_json())
        assert isinstance(parsed, dict)
        assert "alert_id" in parsed
        assert "timestamp" in parsed

    def test_severity_validates_literal(self) -> None:
        with pytest.raises(Exception):  # noqa: B017
            SecurityAlert(
                source_project="test",
                rule_id="T-001",
                severity="invalid",  # type: ignore[arg-type]
                title="Test",
                description="Test",
                affected_asset="test",
            )

    def test_two_alerts_have_unique_ids(self) -> None:
        a = make_security_alert()
        b = make_security_alert()
        assert a.alert_id != b.alert_id


class TestMakeSecurityAlert:
    """Test the fixture factory itself."""

    def test_defaults_are_sensible(self) -> None:
        alert = make_security_alert()
        assert alert.source_project == "test-project"
        assert alert.rule_id == "TEST-001"
        assert alert.severity == "medium"

    def test_overrides_work(self) -> None:
        alert = make_security_alert(severity="critical", user="admin")
        assert alert.severity == "critical"
        assert alert.user == "admin"
