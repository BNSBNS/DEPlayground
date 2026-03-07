"""Tests for attack taxonomy."""

from __future__ import annotations

from src.classifier.taxonomy import (
    ATTACK_TYPES,
    MITRE_MAPPING,
    OWASP_MAPPING,
    AttackType,
)


class TestAttackType:
    def test_all_types_exist(self) -> None:
        assert len(AttackType) == 7

    def test_benign_is_member(self) -> None:
        assert AttackType.BENIGN == "benign"

    def test_attack_types_exclude_benign(self) -> None:
        assert AttackType.BENIGN not in ATTACK_TYPES
        assert len(ATTACK_TYPES) == 6

    def test_owasp_mapping_complete(self) -> None:
        for attack_type in AttackType:
            assert attack_type in OWASP_MAPPING

    def test_mitre_mapping_complete(self) -> None:
        for attack_type in AttackType:
            assert attack_type in MITRE_MAPPING

    def test_attack_types_are_strings(self) -> None:
        for attack_type in AttackType:
            assert isinstance(attack_type.value, str)

    def test_owasp_llm01_mapping(self) -> None:
        assert "LLM01" in OWASP_MAPPING[AttackType.PROMPT_INJECTION]
        assert "LLM01" in OWASP_MAPPING[AttackType.JAILBREAK]
        assert "LLM01" in OWASP_MAPPING[AttackType.INDIRECT_INJECTION]

    def test_mitre_atlas_ids(self) -> None:
        for attack_type in ATTACK_TYPES:
            assert MITRE_MAPPING[attack_type].startswith("AML.")
