"""Tests for data masking strategies."""

from __future__ import annotations

from src.models import MaskingStrategy
from src.protection.masking import (
    apply_masking,
    full_redact,
    mask_credit_card,
    mask_email,
    mask_name,
    mask_phone,
)


class TestMaskEmail:
    def test_standard_email(self) -> None:
        result = mask_email("alice@example.com")
        assert result.endswith("@example.com")
        assert result.startswith("a***")

    def test_single_char_local(self) -> None:
        result = mask_email("a@b.com")
        assert "***" in result
        assert result.endswith("@b.com")

    def test_no_at_sign(self) -> None:
        result = mask_email("notanemail")
        assert result == "***"

    def test_original_not_in_result(self) -> None:
        result = mask_email("bob.smith@company.co.uk")
        assert "bob.smith" not in result


class TestMaskPhone:
    def test_keeps_last_4(self) -> None:
        result = mask_phone("+6591234567")
        assert result.endswith("4567")
        assert "***" in result

    def test_plain_digits(self) -> None:
        result = mask_phone("98765432")
        assert result.endswith("5432")

    def test_formatted_phone(self) -> None:
        result = mask_phone("(555) 123-4567")
        assert result.endswith("4567")

    def test_short_number(self) -> None:
        result = mask_phone("123")
        assert result == "***"

    def test_original_digits_not_exposed(self) -> None:
        result = mask_phone("91234567")
        assert "912" not in result


class TestMaskCreditCard:
    def test_visa_masked(self) -> None:
        result = mask_credit_card("4111111111111111")
        assert result.endswith("1111")
        assert result.startswith("****")

    def test_original_not_in_result(self) -> None:
        result = mask_credit_card("4111111111111111")
        assert "41111111" not in result

    def test_short_card(self) -> None:
        result = mask_credit_card("123")
        assert "****" in result


class TestMaskName:
    def test_keeps_first_letter(self) -> None:
        result = mask_name("Alice")
        assert result.startswith("A")
        assert "***" in result

    def test_empty_name(self) -> None:
        result = mask_name("")
        assert result == "***"

    def test_lowercase_capitalized(self) -> None:
        result = mask_name("bob")
        assert result.startswith("B")


class TestFullRedact:
    def test_returns_placeholder(self) -> None:
        assert full_redact("anything") == "[REDACTED]"

    def test_empty_string(self) -> None:
        assert full_redact("") == "[REDACTED]"


class TestApplyMasking:
    def test_email_strategy(self) -> None:
        result = apply_masking("alice@example.com", MaskingStrategy.EMAIL)
        assert result.strategy == MaskingStrategy.EMAIL
        assert "@example.com" in result.masked_value

    def test_phone_strategy(self) -> None:
        result = apply_masking("+6591234567", MaskingStrategy.PHONE)
        assert result.strategy == MaskingStrategy.PHONE

    def test_credit_card_strategy(self) -> None:
        result = apply_masking("4111111111111111", MaskingStrategy.CREDIT_CARD)
        assert result.strategy == MaskingStrategy.CREDIT_CARD

    def test_name_strategy(self) -> None:
        result = apply_masking("Alice Smith", MaskingStrategy.NAME)
        assert result.strategy == MaskingStrategy.NAME

    def test_full_redact_strategy(self) -> None:
        result = apply_masking("secret", MaskingStrategy.FULL_REDACT)
        assert result.masked_value == "[REDACTED]"

    def test_none_strategy_passthrough(self) -> None:
        result = apply_masking("public-data", MaskingStrategy.NONE)
        assert result.masked_value == "public-data"

    def test_original_length_tracked(self) -> None:
        result = apply_masking("alice@example.com", MaskingStrategy.EMAIL)
        assert result.original_length == len("alice@example.com")

    def test_masked_never_exposes_full_original(self) -> None:
        original = "4111111111111111"
        result = apply_masking(original, MaskingStrategy.CREDIT_CARD)
        assert original not in result.masked_value
