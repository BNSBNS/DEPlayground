"""Tests for the output scanner (PII + prompt leak detection)."""

from __future__ import annotations

import pytest

from src.output_scanner.scanner import OutputScanner, OutputScanResult, PIIMatch


@pytest.fixture()
def scanner() -> OutputScanner:
    return OutputScanner()


class TestPIIMatch:
    def test_fields(self) -> None:
        m = PIIMatch(pii_type="email", value="test@example.com", start=0, end=16)
        assert m.pii_type == "email"
        assert m.value == "test@example.com"


class TestOutputScannerClean:
    def test_clean_text_not_flagged(self, scanner: OutputScanner) -> None:
        result = scanner.scan("The weather is sunny today with no issues.")
        assert not result.flagged
        assert not result.pii_matches
        assert not result.prompt_leak_detected

    def test_returns_output_scan_result(self, scanner: OutputScanner) -> None:
        result = scanner.scan("Hello world")
        assert isinstance(result, OutputScanResult)
        assert result.text == "Hello world"


class TestPIIDetection:
    def test_detects_email(self, scanner: OutputScanner) -> None:
        result = scanner.scan("Contact us at user@example.com for help.")
        assert result.flagged
        emails = [m for m in result.pii_matches if m.pii_type == "email"]
        assert len(emails) == 1
        assert "user@example.com" in emails[0].value

    def test_detects_phone(self, scanner: OutputScanner) -> None:
        result = scanner.scan("Call 555-867-5309 for support.")
        assert result.flagged
        phones = [m for m in result.pii_matches if m.pii_type == "phone_us"]
        assert len(phones) >= 1

    def test_detects_ssn(self, scanner: OutputScanner) -> None:
        result = scanner.scan("SSN: 123-45-6789 is on file.")
        assert result.flagged
        ssns = [m for m in result.pii_matches if m.pii_type == "ssn"]
        assert len(ssns) == 1

    def test_detects_multiple_pii_types(self, scanner: OutputScanner) -> None:
        result = scanner.scan("Email: alice@corp.com, Phone: 123-456-7890")
        assert result.flagged
        types = {m.pii_type for m in result.pii_matches}
        assert "email" in types

    def test_no_pii_in_clean_text(self, scanner: OutputScanner) -> None:
        result = scanner.scan("Python was created by Guido van Rossum in 1991.")
        pii = result.pii_matches
        # No emails or SSNs expected
        assert not any(m.pii_type in {"email", "ssn"} for m in pii)

    def test_pii_positions_correct(self, scanner: OutputScanner) -> None:
        text = "Email: user@test.com is here"
        result = scanner.scan(text)
        emails = [m for m in result.pii_matches if m.pii_type == "email"]
        assert len(emails) >= 1
        m = emails[0]
        assert text[m.start : m.end] == m.value


class TestPromptLeakDetection:
    def test_detects_instructions_leak(self, scanner: OutputScanner) -> None:
        result = scanner.scan("My instructions are to always be helpful and honest.")
        assert result.prompt_leak_detected
        assert result.flagged

    def test_detects_system_prompt_reveal(self, scanner: OutputScanner) -> None:
        result = scanner.scan("The system prompt says: you must be a helpful assistant.")
        assert result.prompt_leak_detected

    def test_detects_programmed_to(self, scanner: OutputScanner) -> None:
        result = scanner.scan("I was instructed to keep this confidential.")
        assert result.prompt_leak_detected

    def test_no_leak_in_normal_response(self, scanner: OutputScanner) -> None:
        result = scanner.scan("The answer is 42. Hope that helps!")
        assert not result.prompt_leak_detected

    def test_flagged_when_leak_detected(self, scanner: OutputScanner) -> None:
        result = scanner.scan("My system prompt is to assist all users.")
        assert result.flagged
