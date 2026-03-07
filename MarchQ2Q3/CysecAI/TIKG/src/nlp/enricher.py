"""NLP text enricher — regex NER with optional SpaCy enhancement.

Extracts entities from CVE descriptions:
- CVE IDs     → link to known CVEs
- CWE IDs     → link to weakness nodes
- Software names (vendor/product patterns)
- Vulnerability type labels (RCE, XSS, SQLi, …)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

_CVE_RE = re.compile(r"\bCVE-\d{4}-\d{4,7}\b", re.IGNORECASE)
_CWE_RE = re.compile(r"\bCWE-\d+\b", re.IGNORECASE)

# Common vulnerability type keywords
_VULN_TYPE_PATTERNS: dict[str, re.Pattern[str]] = {
    "remote_code_execution": re.compile(
        r"\b(?:remote\s+code\s+execution|RCE|arbitrary\s+code\s+execution)\b",
        re.IGNORECASE,
    ),
    "sql_injection": re.compile(r"\b(?:SQL\s+injection|SQLi)\b", re.IGNORECASE),
    "xss": re.compile(
        r"\b(?:cross[-\s]site\s+scripting|XSS)\b",
        re.IGNORECASE,
    ),
    "buffer_overflow": re.compile(r"\b(?:buffer\s+overflow|stack\s+overflow)\b", re.IGNORECASE),
    "path_traversal": re.compile(
        r"\b(?:path\s+traversal|directory\s+traversal|\.\.\/)\b",
        re.IGNORECASE,
    ),
    "privilege_escalation": re.compile(
        r"\b(?:privilege\s+escalation|escalation\s+of\s+privilege|EoP)\b",
        re.IGNORECASE,
    ),
    "denial_of_service": re.compile(
        r"\b(?:denial[\s-]of[\s-]service|DoS|DDoS|crash)\b",
        re.IGNORECASE,
    ),
    "ssrf": re.compile(
        r"\b(?:server[\s-]side\s+request\s+forgery|SSRF)\b",
        re.IGNORECASE,
    ),
    "xxe": re.compile(r"\b(?:XML\s+external\s+entity|XXE)\b", re.IGNORECASE),
    "deserialization": re.compile(r"\b(?:deserialization|unsafe\s+deserializ)\b", re.IGNORECASE),
}

# Well-known vendor name patterns (extend as needed)
_VENDOR_RE = re.compile(
    r"\b(?:Apache|Microsoft|Google|Oracle|Cisco|VMware|Adobe|Linux|OpenSSL|"
    r"WordPress|Drupal|Joomla|Spring|Log4j|Jackson|Struts|Nginx|OpenSSH)\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ExtractedEntity:
    """A named entity extracted from text."""

    entity_type: str  # "cve_ref", "cwe_ref", "vendor", "vuln_type"
    value: str
    start: int
    end: int


@dataclass
class EnrichmentResult:
    """Result of enriching a piece of text."""

    text: str
    cve_refs: list[str] = field(default_factory=list)
    cwe_refs: list[str] = field(default_factory=list)
    vendors: list[str] = field(default_factory=list)
    vuln_types: list[str] = field(default_factory=list)
    entities: list[ExtractedEntity] = field(default_factory=list)


# ---------------------------------------------------------------------------
# TextEnricher
# ---------------------------------------------------------------------------


class TextEnricher:
    """Regex-based NLP enricher. SpaCy can be enabled for enhanced NER."""

    def __init__(self, *, use_spacy: bool = False, spacy_model: str = "en_core_web_sm") -> None:
        self._nlp: Any = None
        if use_spacy:
            self._load_spacy(spacy_model)

    def _load_spacy(self, model: str) -> None:
        """Attempt to load SpaCy model (graceful degradation on failure)."""
        try:
            import spacy  # noqa: PLC0415

            self._nlp = spacy.load(model)
        except Exception:
            self._nlp = None

    def enrich(self, text: str) -> EnrichmentResult:
        """Extract entities from CVE description text."""
        result = EnrichmentResult(text=text)

        # CVE references
        for m in _CVE_RE.finditer(text):
            cve_id = m.group().upper()
            result.cve_refs.append(cve_id)
            result.entities.append(ExtractedEntity("cve_ref", cve_id, m.start(), m.end()))

        # CWE references
        for m in _CWE_RE.finditer(text):
            cwe_id = m.group().upper()
            result.cwe_refs.append(cwe_id)
            result.entities.append(ExtractedEntity("cwe_ref", cwe_id, m.start(), m.end()))

        # Vendor names
        seen_vendors: set[str] = set()
        for m in _VENDOR_RE.finditer(text):
            vendor = m.group()
            if vendor.lower() not in seen_vendors:
                seen_vendors.add(vendor.lower())
                result.vendors.append(vendor)
                result.entities.append(ExtractedEntity("vendor", vendor, m.start(), m.end()))

        # Vulnerability types
        for vuln_type, pattern in _VULN_TYPE_PATTERNS.items():
            if pattern.search(text):
                result.vuln_types.append(vuln_type)

        # Optional SpaCy NER (enhances vendor/org extraction)
        if self._nlp is not None:
            self._spacy_enhance(text, result)

        return result

    def _spacy_enhance(self, text: str, result: EnrichmentResult) -> None:
        """Add SpaCy-detected ORG entities as additional vendors."""
        doc = self._nlp(text)
        seen = {v.lower() for v in result.vendors}
        for ent in doc.ents:
            if ent.label_ in ("ORG", "PRODUCT") and ent.text.lower() not in seen:
                seen.add(ent.text.lower())
                result.vendors.append(ent.text)
                result.entities.append(
                    ExtractedEntity("vendor", ent.text, ent.start_char, ent.end_char)
                )
