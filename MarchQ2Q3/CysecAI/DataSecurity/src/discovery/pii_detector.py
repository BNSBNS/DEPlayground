"""PII detection via regex patterns and column name heuristics."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from src.models import PIIType

# Fallback patterns if YAML config is not available
_DEFAULT_COLUMN_HINTS: dict[PIIType, list[str]] = {
    PIIType.EMAIL: ["email", "email_address", "e_mail", "mail"],
    PIIType.PHONE: ["phone", "phone_number", "mobile", "tel", "telephone", "contact_number"],
    PIIType.NRIC: ["nric", "nric_number", "ic", "id_number", "national_id", "identity"],
    PIIType.SSN: ["ssn", "social_security", "social_security_number"],
    PIIType.CREDIT_CARD: ["credit_card", "card_number", "cc_number", "pan", "payment_card"],
    PIIType.IP_ADDRESS: ["ip", "ip_address", "source_ip", "remote_addr"],
    PIIType.DATE_OF_BIRTH: ["dob", "date_of_birth", "birth_date", "birthdate", "birthday"],
    PIIType.NAME: [
        "name",
        "full_name",
        "first_name",
        "last_name",
        "given_name",
        "surname",
        "patient_name",
        "customer_name",
    ],
    PIIType.ADDRESS: [
        "address",
        "street",
        "street_address",
        "home_address",
        "residential_address",
        "postal_address",
    ],
}

_DEFAULT_REGEXES: dict[PIIType, str] = {
    PIIType.EMAIL: r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$",
    PIIType.PHONE: r"^[\+]?[(]?[0-9]{3}[)]?[-\s\.]?[0-9]{3}[-\s\.]?[0-9]{4,6}$",
    PIIType.NRIC: r"^[STFGM][0-9]{7}[A-Z]$",
    PIIType.SSN: r"^[0-9]{3}-[0-9]{2}-[0-9]{4}$",
    PIIType.CREDIT_CARD: (
        r"^(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}"
        r"|3(?:0[0-5]|[68][0-9])[0-9]{11}|6(?:011|5[0-9]{2})[0-9]{12})$"
    ),
    PIIType.IP_ADDRESS: (
        r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}"
        r"(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"
    ),
    PIIType.DATE_OF_BIRTH: r"^[0-9]{4}[-/][0-9]{1,2}[-/][0-9]{1,2}$",
}


class PIIDetector:
    """Detect PII in column names and data samples using configurable patterns."""

    def __init__(self, config_path: str | None = None) -> None:
        self._column_hints = dict(_DEFAULT_COLUMN_HINTS)
        self._regexes = dict(_DEFAULT_REGEXES)
        self._compiled: dict[PIIType, re.Pattern[str]] = {}

        if config_path:
            self._load_yaml_config(config_path)

        # Compile all regex patterns
        for pii_type, pattern in self._regexes.items():
            self._compiled[pii_type] = re.compile(pattern, re.IGNORECASE)

    def _load_yaml_config(self, config_path: str) -> None:
        """Load PII patterns from a YAML configuration file."""
        path = Path(config_path)
        if not path.exists():
            return
        with path.open() as f:
            data: dict[str, Any] = yaml.safe_load(f) or {}

        for entry in data.get("patterns", []):
            pii_type_str = str(entry.get("type", "")).lower()
            try:
                pii_type = PIIType(pii_type_str)
            except ValueError:
                continue
            if "regex" in entry:
                self._regexes[pii_type] = str(entry["regex"])
            if "column_hints" in entry:
                self._column_hints[pii_type] = [str(h) for h in entry["column_hints"]]

    def detect_from_column_name(self, column_name: str) -> list[PIIType]:
        """Detect likely PII types from a column name alone."""
        lower = column_name.lower().strip()
        matches: list[PIIType] = []
        for pii_type, hints in self._column_hints.items():
            if any(hint in lower for hint in hints):
                matches.append(pii_type)
        return matches

    def detect_from_value(self, value: str) -> list[PIIType]:
        """Detect PII types by matching a value against regex patterns."""
        matches: list[PIIType] = []
        for pii_type, pattern in self._compiled.items():
            if pattern.match(value.strip()):
                matches.append(pii_type)
        return matches

    def detect(self, column_name: str, sample_values: list[str] | None = None) -> list[PIIType]:
        """Detect PII using column name heuristics first, then sample values."""
        matches = set(self.detect_from_column_name(column_name))
        if sample_values:
            for value in sample_values[:20]:  # limit to first 20 samples
                if value:
                    matches.update(self.detect_from_value(str(value)))
        return list(matches)


# Module-level default instance
_default_detector: PIIDetector | None = None


def get_detector(config_path: str | None = None) -> PIIDetector:
    """Return the default PIIDetector, loading config if provided."""
    global _default_detector
    if _default_detector is None or config_path:
        _default_detector = PIIDetector(config_path)
    return _default_detector
