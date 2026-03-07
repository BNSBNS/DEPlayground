"""Tests for column classification."""

from __future__ import annotations

from src.discovery.classification import classify_column, get_masking_strategy
from src.models import DataClassification, MaskingStrategy, PIIType


class TestClassifyColumn:
    def test_public_when_no_pii(self) -> None:
        classification, masking = classify_column("id", [])
        assert classification == DataClassification.PUBLIC
        assert masking == MaskingStrategy.NONE

    def test_pii_email(self) -> None:
        classification, masking = classify_column("email", [PIIType.EMAIL])
        assert classification == DataClassification.PII
        assert masking == MaskingStrategy.EMAIL

    def test_pii_phone(self) -> None:
        classification, _ = classify_column("phone", [PIIType.PHONE])
        assert classification == DataClassification.PII

    def test_pci_credit_card(self) -> None:
        classification, masking = classify_column("credit_card", [PIIType.CREDIT_CARD])
        assert classification == DataClassification.PCI
        assert masking == MaskingStrategy.CREDIT_CARD

    def test_phi_diagnosis_column(self) -> None:
        classification, masking = classify_column("diagnosis", [PIIType.UNKNOWN])
        assert classification == DataClassification.PHI
        assert masking == MaskingStrategy.FULL_REDACT

    def test_phi_patient_name(self) -> None:
        classification, _ = classify_column("patient_name", [PIIType.NAME])
        assert classification == DataClassification.PHI

    def test_nric_full_redact(self) -> None:
        _, masking = classify_column("nric", [PIIType.NRIC])
        assert masking == MaskingStrategy.FULL_REDACT

    def test_address_full_redact(self) -> None:
        _, masking = classify_column("address", [PIIType.ADDRESS])
        assert masking == MaskingStrategy.FULL_REDACT


class TestGetMaskingStrategy:
    def test_email_strategy(self) -> None:
        assert get_masking_strategy(PIIType.EMAIL) == MaskingStrategy.EMAIL

    def test_phone_strategy(self) -> None:
        assert get_masking_strategy(PIIType.PHONE) == MaskingStrategy.PHONE

    def test_credit_card_strategy(self) -> None:
        assert get_masking_strategy(PIIType.CREDIT_CARD) == MaskingStrategy.CREDIT_CARD

    def test_nric_strategy(self) -> None:
        assert get_masking_strategy(PIIType.NRIC) == MaskingStrategy.FULL_REDACT

    def test_unknown_fallback(self) -> None:
        assert get_masking_strategy(PIIType.UNKNOWN) == MaskingStrategy.FULL_REDACT
