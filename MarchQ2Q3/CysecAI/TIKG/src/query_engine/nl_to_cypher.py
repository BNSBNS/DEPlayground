"""NL-to-Cypher query engine — template-based intent matching.

Converts natural language questions about the threat graph into Cypher queries.
Supports common patterns:
- CVE lookup by ID
- CVEs by severity / CVSS score
- CVEs for a vendor/product
- ATT&CK techniques by tactic
- KEV status of a CVE
- Most critical CVEs (top-N by base_score)
- Techniques that exploit a CVE
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class QueryResult:
    """Result of a NL-to-Cypher translation."""

    natural_language: str
    cypher: str
    parameters: dict[str, Any]
    intent: str
    confidence: float  # 0-1


# ---------------------------------------------------------------------------
# Intent patterns
# ---------------------------------------------------------------------------

_PATTERNS: list[tuple[str, str, re.Pattern[str]]] = [
    (
        "cve_by_id",
        "Fetch details for a specific CVE",
        re.compile(r"\bCVE-\d{4}-\d{4,7}\b", re.IGNORECASE),
    ),
    (
        "top_cves",
        "Top-N most critical CVEs by score",
        re.compile(r"\btop[\s-]*\d+\b.*\b(?:CVE|vulnerabilit|critical)", re.IGNORECASE),
    ),
    (
        "kev_status",
        "Check if a CVE is in the CISA KEV catalog",
        re.compile(r"\b(?:KEV|known\s+exploit\w*|actively\s+exploit\w*)\b", re.IGNORECASE),
    ),
    (
        "critical_cves",
        "List critical severity CVEs",
        re.compile(r"\bcritical\b.*\bCVE", re.IGNORECASE),
    ),
    (
        "high_cves",
        "List high severity CVEs",
        re.compile(r"\bhigh\b.*\b(?:CVE|vulnerabilit)", re.IGNORECASE),
    ),
    (
        "cves_for_vendor",
        "CVEs affecting a specific vendor/product",
        re.compile(
            r"\b(?:affect|impact|vulnerabilit).*\b(?:vendor|product|software|apache|"
            r"microsoft|log4j|spring|nginx|openssl)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "techniques_by_tactic",
        "ATT&CK techniques for a tactic",
        re.compile(
            r"\b(?:technique|attack).*\b(?:tactic|execution|persistence|privilege|lateral|"
            r"exfiltration|collection|command|discovery|defense)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "techniques_for_cve",
        "Attack techniques that exploit a CVE",
        re.compile(r"\b(?:technique|attack)\b.*\bCVE-\d{4}-\d{4,7}\b", re.IGNORECASE),
    ),
    (
        "epss_high",
        "CVEs with high EPSS exploitation probability",
        re.compile(r"\bEPSS\b", re.IGNORECASE),
    ),
]

# ---------------------------------------------------------------------------
# Cypher templates
# ---------------------------------------------------------------------------

_CYPHER: dict[str, str] = {
    "cve_by_id": (
        "MATCH (c:CVE {cve_id: $cve_id}) "
        "OPTIONAL MATCH (c)-[:HAS_WEAKNESS]->(w:CWE) "
        "OPTIONAL MATCH (c)-[:EXPLOITED_BY]->(k:KEVEntry) "
        "RETURN c, collect(w) AS weaknesses, k"
    ),
    "critical_cves": (
        "MATCH (c:CVE {severity: 'CRITICAL'}) RETURN c ORDER BY c.base_score DESC LIMIT $limit"
    ),
    "high_cves": (
        "MATCH (c:CVE) WHERE c.severity IN ['HIGH', 'CRITICAL'] "
        "RETURN c ORDER BY c.base_score DESC LIMIT $limit"
    ),
    "top_cves": (
        "MATCH (c:CVE) WHERE c.base_score IS NOT NULL "
        "RETURN c ORDER BY c.base_score DESC LIMIT $limit"
    ),
    "kev_status": (
        "MATCH (c:CVE)-[:EXPLOITED_BY]->(k:KEVEntry) "
        "RETURN c.cve_id, c.severity, c.base_score, "
        "k.vulnerability_name, k.date_added ORDER BY k.date_added DESC LIMIT $limit"
    ),
    "cves_for_vendor": (
        "MATCH (c:CVE)-[:AFFECTS]->(s:Software) "
        "WHERE toLower(s.vendor) CONTAINS toLower($vendor) "
        "OR toLower(s.product) CONTAINS toLower($product) "
        "RETURN c, s ORDER BY c.base_score DESC LIMIT $limit"
    ),
    "techniques_by_tactic": (
        "MATCH (t:AttackTechnique {tactic: $tactic}) RETURN t ORDER BY t.technique_id LIMIT $limit"
    ),
    "techniques_for_cve": (
        "MATCH (t:AttackTechnique)-[:EXPLOITS]->(c:CVE {cve_id: $cve_id}) RETURN t, c"
    ),
    "epss_high": (
        "MATCH (c:CVE) WHERE c.epss_score >= $threshold "
        "RETURN c ORDER BY c.epss_score DESC LIMIT $limit"
    ),
    "unknown": "RETURN 'Query not understood. Please refine your question.' AS message",
}


# ---------------------------------------------------------------------------
# Parameter extractors
# ---------------------------------------------------------------------------


def _extract_cve_id(text: str) -> str | None:
    m = re.search(r"\bCVE-\d{4}-\d{4,7}\b", text, re.IGNORECASE)
    return m.group().upper() if m else None


def _extract_top_n(text: str, default: int = 10) -> int:
    m = re.search(r"\btop[\s-]*(\d+)\b", text, re.IGNORECASE)
    return int(m.group(1)) if m else default


def _extract_tactic(text: str) -> str:
    tactics = [
        "execution",
        "persistence",
        "privilege-escalation",
        "defense-evasion",
        "credential-access",
        "discovery",
        "lateral-movement",
        "collection",
        "command-and-control",
        "exfiltration",
        "impact",
    ]
    text_lower = text.lower()
    for tactic in tactics:
        if tactic.replace("-", " ") in text_lower or tactic in text_lower:
            return tactic
    return "execution"  # default


def _extract_vendor(text: str) -> str:
    known = [
        "apache",
        "microsoft",
        "google",
        "oracle",
        "cisco",
        "log4j",
        "spring",
        "nginx",
        "openssl",
        "linux",
        "wordpress",
    ]
    text_lower = text.lower()
    for vendor in known:
        if vendor in text_lower:
            return vendor
    return ""


# ---------------------------------------------------------------------------
# NLQueryEngine
# ---------------------------------------------------------------------------


class NLQueryEngine:
    """Translates natural language questions into Cypher queries."""

    def translate(self, question: str) -> QueryResult:
        """Match the question to an intent and build a parameterised Cypher query."""
        intent, confidence = self._classify(question)
        cypher, params = self._build_query(intent, question)
        return QueryResult(
            natural_language=question,
            cypher=cypher,
            parameters=params,
            intent=intent,
            confidence=confidence,
        )

    def _classify(self, text: str) -> tuple[str, float]:
        """Return (intent, confidence) for the best-matching pattern."""
        for intent, _desc, pattern in _PATTERNS:
            if pattern.search(text):
                return intent, 0.85
        return "unknown", 0.0

    def _build_query(self, intent: str, question: str) -> tuple[str, dict[str, Any]]:
        cypher = _CYPHER.get(intent, _CYPHER["unknown"])
        params: dict[str, Any] = {"limit": 10}

        if intent == "cve_by_id":
            cve_id = _extract_cve_id(question) or ""
            params["cve_id"] = cve_id

        elif intent == "top_cves":
            params["limit"] = _extract_top_n(question)

        elif intent == "kev_status":
            kev_cve_id = _extract_cve_id(question)
            if kev_cve_id:
                cypher = "MATCH (c:CVE {cve_id: $cve_id})-[:EXPLOITED_BY]->(k:KEVEntry) RETURN c, k"
                params["cve_id"] = kev_cve_id

        elif intent == "cves_for_vendor":
            vendor = _extract_vendor(question)
            params["vendor"] = vendor
            params["product"] = vendor

        elif intent == "techniques_by_tactic":
            params["tactic"] = _extract_tactic(question)

        elif intent == "techniques_for_cve":
            params["cve_id"] = _extract_cve_id(question) or ""

        elif intent == "epss_high":
            params["threshold"] = 0.7

        return cypher, params
