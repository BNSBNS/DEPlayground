"""Alert builder — converts ScanResult into a SecurityAlert for Kafka emission."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from cysec_shared.models.alerts import SecurityAlert
from src.classifier.taxonomy import MITRE_MAPPING, AttackType

if TYPE_CHECKING:
    from src.guardrail.scanner import ScanResult

# Map attack type to SecurityAlert severity literal
_SEVERITY: dict[AttackType, Literal["critical", "high", "medium", "low", "info"]] = {
    AttackType.PROMPT_INJECTION: "high",
    AttackType.JAILBREAK: "high",
    AttackType.DATA_EXFILTRATION: "critical",
    AttackType.PII_EXTRACTION: "high",
    AttackType.ROLE_HIJACKING: "medium",
    AttackType.INDIRECT_INJECTION: "high",
    AttackType.BENIGN: "info",
}


def build_alert(result: ScanResult) -> SecurityAlert:
    """Create a SecurityAlert from a blocked ScanResult."""
    attack = AttackType(result.attack_type)
    severity = _SEVERITY.get(attack, "medium")
    mitre_id = MITRE_MAPPING.get(attack) or None

    return SecurityAlert(
        source_project="AIMMLSecurity",
        rule_id=f"aiml_{result.attack_type}",
        severity=severity,
        title=f"LLM Attack Detected: {result.attack_type.replace('_', ' ').title()}",
        description=(
            f"Blocked {result.attack_type} with confidence {result.confidence:.2%}. "
            f"Prompt truncated: {result.text[:80]!r}"
        ),
        mitre_technique_id=mitre_id,
        evidence={
            "attack_type": result.attack_type,
            "confidence": result.confidence,
            "blocked": result.blocked,
            "text_preview": result.text[:100],
        },
        affected_asset="llm_api",
        recommendations=[
            "Review and sanitise user input before forwarding to LLM",
            "Apply additional prompt hardening to system instructions",
        ],
    )
