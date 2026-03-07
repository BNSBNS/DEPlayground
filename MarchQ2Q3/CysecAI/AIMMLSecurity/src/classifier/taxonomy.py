"""Attack taxonomy — OWASP LLM Top 10 mapped attack types."""

from __future__ import annotations

from enum import StrEnum


class AttackType(StrEnum):
    """LLM attack categories mapped to OWASP LLM Top 10."""

    PROMPT_INJECTION = "prompt_injection"  # LLM01
    JAILBREAK = "jailbreak"  # LLM01
    DATA_EXFILTRATION = "data_exfiltration"  # LLM02
    PII_EXTRACTION = "pii_extraction"  # LLM02
    ROLE_HIJACKING = "role_hijacking"  # LLM07
    INDIRECT_INJECTION = "indirect_injection"  # LLM01
    BENIGN = "benign"


# OWASP LLM Top 10 mapping
OWASP_MAPPING: dict[AttackType, str] = {
    AttackType.PROMPT_INJECTION: "LLM01 - Prompt Injection",
    AttackType.JAILBREAK: "LLM01 - Prompt Injection",
    AttackType.DATA_EXFILTRATION: "LLM02 - Insecure Output Handling",
    AttackType.PII_EXTRACTION: "LLM02 - Insecure Output Handling",
    AttackType.ROLE_HIJACKING: "LLM07 - Insecure Plugin Design",
    AttackType.INDIRECT_INJECTION: "LLM01 - Prompt Injection",
    AttackType.BENIGN: "N/A",
}

# MITRE ATLAS mapping
MITRE_MAPPING: dict[AttackType, str] = {
    AttackType.PROMPT_INJECTION: "AML.T0051",
    AttackType.JAILBREAK: "AML.T0054",
    AttackType.DATA_EXFILTRATION: "AML.T0024",
    AttackType.PII_EXTRACTION: "AML.T0024",
    AttackType.ROLE_HIJACKING: "AML.T0051",
    AttackType.INDIRECT_INJECTION: "AML.T0051",
    AttackType.BENIGN: "",
}

ATTACK_TYPES = [t for t in AttackType if t != AttackType.BENIGN]
