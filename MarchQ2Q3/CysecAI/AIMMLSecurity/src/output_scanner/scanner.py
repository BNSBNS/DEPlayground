"""Output scanner — detects PII and system prompt leaks in LLM responses."""

from __future__ import annotations

import re

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# PII patterns
# ---------------------------------------------------------------------------

_PII_PATTERNS: dict[str, re.Pattern[str]] = {
    "email": re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"),
    "phone_us": re.compile(r"\b(?:\+1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    "credit_card": re.compile(r"\b(?:\d[ -]?){13,16}\b"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "ipv4": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    "api_key": re.compile(r"\b(?:sk|pk|api|key)[-_][A-Za-z0-9]{16,}\b", re.IGNORECASE),
}

# Phrases that suggest the LLM is revealing its system prompt
_LEAK_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"my\s+(?:system\s+)?instructions\s+(?:are|say|state)", re.IGNORECASE),
    re.compile(r"(?:system\s+)?prompt\s+(?:is|says|states|reads)", re.IGNORECASE),
    re.compile(r"i\s+(?:was|am)\s+(?:instructed|told|programmed)\s+to", re.IGNORECASE),
    re.compile(r"(?:my\s+)?(?:guidelines|constraints|rules)\s+(?:are|state|say)", re.IGNORECASE),
    re.compile(r"confidential.*?(?:instructions|prompt|system)", re.IGNORECASE),
    re.compile(r"do\s+not\s+(?:reveal|share|disclose)\s+(?:this|my|the)", re.IGNORECASE),
]


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class PIIMatch(BaseModel):
    """A single PII match found in the output."""

    pii_type: str
    value: str
    start: int
    end: int


class OutputScanResult(BaseModel):
    """Result of scanning an LLM output."""

    text: str
    pii_matches: list[PIIMatch]
    prompt_leak_detected: bool
    flagged: bool  # True if any issue found


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------


class OutputScanner:
    """Scans LLM outputs for PII and system prompt leaks."""

    def scan(self, text: str) -> OutputScanResult:
        pii_matches = self._detect_pii(text)
        leak = self._detect_prompt_leak(text)
        return OutputScanResult(
            text=text,
            pii_matches=pii_matches,
            prompt_leak_detected=leak,
            flagged=bool(pii_matches) or leak,
        )

    def _detect_pii(self, text: str) -> list[PIIMatch]:
        matches: list[PIIMatch] = []
        for pii_type, pattern in _PII_PATTERNS.items():
            for m in pattern.finditer(text):
                matches.append(
                    PIIMatch(pii_type=pii_type, value=m.group(), start=m.start(), end=m.end())
                )
        return matches

    def _detect_prompt_leak(self, text: str) -> bool:
        return any(pattern.search(text) is not None for pattern in _LEAK_PATTERNS)
