"""Tests for the alert emitter."""

from __future__ import annotations

import pytest

from cysec_shared.models.alerts import SecurityAlert
from src.alerts.emitter import build_alert
from src.classifier.taxonomy import AttackType
from src.guardrail.scanner import ScanResult


def _make_result(attack_type: str, confidence: float = 0.9, blocked: bool = True) -> ScanResult:
    return ScanResult(
        text=f"Sample text for {attack_type}",
        attack_type=attack_type,
        confidence=confidence,
        blocked=blocked,
        latency_ms=1.5,
    )


class TestBuildAlert:
    def test_returns_security_alert(self) -> None:
        result = _make_result(AttackType.PROMPT_INJECTION)
        alert = build_alert(result)
        assert isinstance(alert, SecurityAlert)

    def test_source_project(self) -> None:
        alert = build_alert(_make_result(AttackType.JAILBREAK))
        assert alert.source_project == "AIMMLSecurity"

    def test_rule_id_contains_attack_type(self) -> None:
        alert = build_alert(_make_result(AttackType.DATA_EXFILTRATION))
        assert "data_exfiltration" in alert.rule_id

    def test_data_exfiltration_is_critical(self) -> None:
        alert = build_alert(_make_result(AttackType.DATA_EXFILTRATION))
        assert alert.severity == "critical"

    def test_prompt_injection_is_high(self) -> None:
        alert = build_alert(_make_result(AttackType.PROMPT_INJECTION))
        assert alert.severity == "high"

    def test_role_hijacking_is_medium(self) -> None:
        alert = build_alert(_make_result(AttackType.ROLE_HIJACKING))
        assert alert.severity == "medium"

    def test_mitre_id_populated(self) -> None:
        alert = build_alert(_make_result(AttackType.JAILBREAK))
        assert alert.mitre_technique_id is not None
        assert alert.mitre_technique_id.startswith("AML.")

    def test_benign_has_info_severity(self) -> None:
        result = _make_result(AttackType.BENIGN, confidence=0.99, blocked=False)
        alert = build_alert(result)
        assert alert.severity == "info"

    def test_evidence_contains_attack_type(self) -> None:
        result = _make_result(AttackType.PII_EXTRACTION)
        alert = build_alert(result)
        assert alert.evidence["attack_type"] == AttackType.PII_EXTRACTION

    def test_confidence_in_evidence(self) -> None:
        result = _make_result(AttackType.INDIRECT_INJECTION, confidence=0.87)
        alert = build_alert(result)
        assert abs(alert.evidence["confidence"] - 0.87) < 1e-9

    def test_alert_has_recommendation(self) -> None:
        alert = build_alert(_make_result(AttackType.PROMPT_INJECTION))
        assert len(alert.recommendations) > 0

    @pytest.mark.parametrize("attack_type", list(AttackType))
    def test_all_attack_types_produce_valid_alert(self, attack_type: AttackType) -> None:
        result = _make_result(attack_type)
        alert = build_alert(result)
        assert alert.severity in {"critical", "high", "medium", "low", "info"}
