"""Tests for PII detection."""

from __future__ import annotations

import pytest

from src.discovery.pii_detector import PIIDetector
from src.models import PIIType


@pytest.fixture()
def detector() -> PIIDetector:
    return PIIDetector()


class TestColumnNameDetection:
    def test_email_column_name(self, detector: PIIDetector) -> None:
        result = detector.detect_from_column_name("email")
        assert PIIType.EMAIL in result

    def test_phone_column_name(self, detector: PIIDetector) -> None:
        result = detector.detect_from_column_name("phone_number")
        assert PIIType.PHONE in result

    def test_nric_column_name(self, detector: PIIDetector) -> None:
        result = detector.detect_from_column_name("nric_number")
        assert PIIType.NRIC in result

    def test_credit_card_column_name(self, detector: PIIDetector) -> None:
        result = detector.detect_from_column_name("credit_card")
        assert PIIType.CREDIT_CARD in result

    def test_name_column(self, detector: PIIDetector) -> None:
        result = detector.detect_from_column_name("full_name")
        assert PIIType.NAME in result

    def test_dob_column(self, detector: PIIDetector) -> None:
        result = detector.detect_from_column_name("date_of_birth")
        assert PIIType.DATE_OF_BIRTH in result

    def test_public_column(self, detector: PIIDetector) -> None:
        result = detector.detect_from_column_name("created_at")
        assert result == []

    def test_id_column_not_pii(self, detector: PIIDetector) -> None:
        result = detector.detect_from_column_name("user_id")
        assert result == []


class TestValueDetection:
    def test_email_value(self, detector: PIIDetector) -> None:
        result = detector.detect_from_value("alice@example.com")
        assert PIIType.EMAIL in result

    def test_invalid_email_not_detected(self, detector: PIIDetector) -> None:
        result = detector.detect_from_value("not-an-email")
        assert PIIType.EMAIL not in result

    def test_nric_value(self, detector: PIIDetector) -> None:
        result = detector.detect_from_value("S1234567A")
        assert PIIType.NRIC in result

    def test_ssn_value(self, detector: PIIDetector) -> None:
        result = detector.detect_from_value("123-45-6789")
        assert PIIType.SSN in result

    def test_credit_card_visa(self, detector: PIIDetector) -> None:
        result = detector.detect_from_value("4111111111111111")
        assert PIIType.CREDIT_CARD in result

    def test_ip_address_value(self, detector: PIIDetector) -> None:
        result = detector.detect_from_value("192.168.1.1")
        assert PIIType.IP_ADDRESS in result

    def test_dob_value(self, detector: PIIDetector) -> None:
        result = detector.detect_from_value("1990-01-15")
        assert PIIType.DATE_OF_BIRTH in result

    def test_random_string_no_match(self, detector: PIIDetector) -> None:
        result = detector.detect_from_value("hello world")
        assert result == []


class TestDetectCombined:
    def test_column_name_wins_no_samples(self, detector: PIIDetector) -> None:
        result = detector.detect("email")
        assert PIIType.EMAIL in result

    def test_samples_add_extra_types(self, detector: PIIDetector) -> None:
        result = detector.detect("col1", sample_values=["alice@example.com"])
        assert PIIType.EMAIL in result

    def test_empty_samples_ok(self, detector: PIIDetector) -> None:
        result = detector.detect("email", sample_values=[])
        assert PIIType.EMAIL in result

    def test_none_samples_ok(self, detector: PIIDetector) -> None:
        result = detector.detect("email", sample_values=None)
        assert PIIType.EMAIL in result
