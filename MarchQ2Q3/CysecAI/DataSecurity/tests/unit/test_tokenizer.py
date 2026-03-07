"""Tests for format-preserving tokenization."""

from __future__ import annotations

import pytest

from src.protection.tokenizer import tokenize_credit_card, tokenize_nric


class TestTokenizeCreditCard:
    def test_same_length_as_original(self) -> None:
        token = tokenize_credit_card("4111111111111111")
        assert len(token) == 16

    def test_preserves_bin(self) -> None:
        token = tokenize_credit_card("4111111111111111")
        assert token[:6] == "411111"

    def test_preserves_last_4(self) -> None:
        token = tokenize_credit_card("4111111111111111")
        assert token[-4:] == "1111"

    def test_deterministic(self) -> None:
        t1 = tokenize_credit_card("4111111111111111", secret="test-secret")
        t2 = tokenize_credit_card("4111111111111111", secret="test-secret")
        assert t1 == t2

    def test_different_secret_different_token(self) -> None:
        t1 = tokenize_credit_card("4111111111111111", secret="secret-a")
        t2 = tokenize_credit_card("4111111111111111", secret="secret-b")
        assert t1 != t2

    def test_different_pan_different_token(self) -> None:
        t1 = tokenize_credit_card("4111111111111111")
        t2 = tokenize_credit_card("5500005555555559")
        assert t1 != t2

    def test_short_pan_returns_placeholder(self) -> None:
        result = tokenize_credit_card("123")
        assert result == "0000000000000000"

    def test_is_not_reversible(self) -> None:
        from src.protection.tokenizer import detokenize_credit_card

        with pytest.raises(NotImplementedError):
            detokenize_credit_card("4111111111111111")


class TestTokenizeNRIC:
    def test_preserves_format(self) -> None:
        token = tokenize_nric("S1234567A")
        assert len(token) == 9
        assert token[0] == "S"
        assert token[-1] == "A"

    def test_deterministic(self) -> None:
        t1 = tokenize_nric("S1234567A", secret="sec")
        t2 = tokenize_nric("S1234567A", secret="sec")
        assert t1 == t2

    def test_invalid_nric_redacted(self) -> None:
        assert tokenize_nric("INVALID") == "[REDACTED]"

    def test_different_nric_different_token(self) -> None:
        t1 = tokenize_nric("S1234567A")
        t2 = tokenize_nric("T7654321B")
        assert t1 != t2
