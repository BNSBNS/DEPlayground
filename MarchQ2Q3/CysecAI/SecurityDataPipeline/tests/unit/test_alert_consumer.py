"""Tests for SecurityAlert consumer/deserializer (Phase 2)."""

from __future__ import annotations

import json

import pytest

from cysec_shared import SecurityAlert
from src.ingestion.alert_consumer import (
    AlertDeserializationError,
    alert_to_normalized_event,
    deserialize_alert,
)


def _sample_alert_dict() -> dict[str, object]:
    """Valid SecurityAlert as a dict."""
    return {
        "alert_id": "test-alert-001",
        "source_project": "FraudAndAnomaly",
        "rule_id": "FRAUD-001",
        "severity": "high",
        "title": "Suspicious Transaction",
        "description": "Large amount from new device",
        "affected_asset": "payment-gateway-01",
        "mitre_technique_id": "T1078",
        "mitre_tactic": "Initial Access",
        "source_ip": "203.0.113.50",
        "evidence": {"amount": 9999.99, "score": 0.95},
        "recommendations": ["Block IP", "Review account"],
    }


class TestDeserializeAlert:
    """deserialize_alert tests."""

    def test_from_dict(self) -> None:
        alert = deserialize_alert(_sample_alert_dict())
        assert isinstance(alert, SecurityAlert)
        assert alert.source_project == "FraudAndAnomaly"
        assert alert.severity == "high"

    def test_from_json_string(self) -> None:
        json_str = json.dumps(_sample_alert_dict())
        alert = deserialize_alert(json_str)
        assert alert.rule_id == "FRAUD-001"

    def test_from_bytes(self) -> None:
        json_bytes = json.dumps(_sample_alert_dict()).encode("utf-8")
        alert = deserialize_alert(json_bytes)
        assert alert.title == "Suspicious Transaction"

    def test_rejects_invalid_json(self) -> None:
        with pytest.raises(AlertDeserializationError, match="Invalid JSON"):
            deserialize_alert("{broken")

    def test_rejects_missing_required_fields(self) -> None:
        with pytest.raises(AlertDeserializationError, match="Invalid SecurityAlert"):
            deserialize_alert({"source_project": "test"})  # missing required fields

    def test_preserves_evidence(self) -> None:
        alert = deserialize_alert(_sample_alert_dict())
        assert alert.evidence["amount"] == 9999.99
        assert alert.evidence["score"] == 0.95

    def test_preserves_recommendations(self) -> None:
        alert = deserialize_alert(_sample_alert_dict())
        assert len(alert.recommendations) == 2


class TestAlertToNormalizedEvent:
    """alert_to_normalized_event tests."""

    def test_converts_alert(self) -> None:
        alert = deserialize_alert(_sample_alert_dict())
        event = alert_to_normalized_event(alert)
        assert event.event_id == "test-alert-001"
        assert event.source == "alert:FraudAndAnomaly"
        assert event.event_type == "security_alert:FRAUD-001"
        assert event.severity == "high"
        assert event.action == "alert"

    def test_preserves_ip(self) -> None:
        alert = deserialize_alert(_sample_alert_dict())
        event = alert_to_normalized_event(alert)
        assert event.src_ip == "203.0.113.50"

    def test_preserves_hostname(self) -> None:
        alert = deserialize_alert(_sample_alert_dict())
        event = alert_to_normalized_event(alert)
        assert event.hostname == "payment-gateway-01"

    def test_details_contain_mitre(self) -> None:
        alert = deserialize_alert(_sample_alert_dict())
        event = alert_to_normalized_event(alert)
        assert event.details["mitre_technique_id"] == "T1078"
        assert event.details["mitre_tactic"] == "Initial Access"

    def test_details_contain_evidence(self) -> None:
        alert = deserialize_alert(_sample_alert_dict())
        event = alert_to_normalized_event(alert)
        assert event.details["evidence"]["amount"] == 9999.99
