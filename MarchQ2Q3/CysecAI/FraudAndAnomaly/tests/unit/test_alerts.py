"""Tests for fraud alert emitter (Phase 6)."""

from __future__ import annotations

import numpy as np

from cysec_shared.models.alerts import SecurityAlert
from src.alerts.emitter import (
    build_alerts_from_predictions,
    build_fraud_alert,
)


class TestBuildFraudAlert:
    """Test individual alert construction."""

    def test_returns_security_alert(self) -> None:
        alert = build_fraud_alert(
            transaction_id="tx-001",
            user_id="user-001",
            score=0.85,
            explanation=[("amount_log", 0.5), ("is_night", 0.3), ("geo_distance", 0.2)],
        )
        assert isinstance(alert, SecurityAlert)

    def test_severity_critical(self) -> None:
        alert = build_fraud_alert("tx-001", "user-001", 0.95, [])
        assert alert.severity == "critical"

    def test_severity_high(self) -> None:
        alert = build_fraud_alert("tx-001", "user-001", 0.75, [])
        assert alert.severity == "high"

    def test_severity_medium(self) -> None:
        alert = build_fraud_alert("tx-001", "user-001", 0.55, [])
        assert alert.severity == "medium"

    def test_severity_low(self) -> None:
        alert = build_fraud_alert("tx-001", "user-001", 0.3, [])
        assert alert.severity == "low"

    def test_source_project(self) -> None:
        alert = build_fraud_alert("tx-001", "user-001", 0.8, [])
        assert alert.source_project == "FraudAndAnomaly"

    def test_evidence_contains_score(self) -> None:
        alert = build_fraud_alert("tx-001", "user-001", 0.8, [("feat", 0.5)])
        assert alert.evidence["fraud_score"] == 0.8
        assert alert.evidence["transaction_id"] == "tx-001"

    def test_mitre_mapping(self) -> None:
        alert = build_fraud_alert("tx-001", "user-001", 0.8, [])
        assert alert.mitre_technique_id == "T1078"

    def test_includes_ip(self) -> None:
        alert = build_fraud_alert("tx-001", "user-001", 0.8, [], ip_address="10.0.0.1")
        assert alert.source_ip == "10.0.0.1"

    def test_recommendations_present(self) -> None:
        alert = build_fraud_alert("tx-001", "user-001", 0.8, [])
        assert len(alert.recommendations) > 0


class TestBuildAlertsFromPredictions:
    """Test batch alert construction."""

    def test_only_flagged_transactions(self) -> None:
        alerts = build_alerts_from_predictions(
            transaction_ids=["tx-1", "tx-2", "tx-3"],
            user_ids=["u1", "u2", "u3"],
            scores=np.array([0.9, 0.1, 0.8]),
            predictions=np.array([1, 0, 1]),
            explanations=[[("f1", 0.5)], [("f1", 0.1)], [("f1", 0.4)]],
        )
        assert len(alerts) == 2

    def test_empty_when_no_fraud(self) -> None:
        alerts = build_alerts_from_predictions(
            transaction_ids=["tx-1"],
            user_ids=["u1"],
            scores=np.array([0.1]),
            predictions=np.array([0]),
            explanations=[[("f1", 0.1)]],
        )
        assert len(alerts) == 0

    def test_all_flagged(self) -> None:
        alerts = build_alerts_from_predictions(
            transaction_ids=["tx-1", "tx-2"],
            user_ids=["u1", "u2"],
            scores=np.array([0.9, 0.8]),
            predictions=np.array([1, 1]),
            explanations=[[("f1", 0.5)], [("f2", 0.4)]],
        )
        assert len(alerts) == 2
