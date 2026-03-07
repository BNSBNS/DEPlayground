"""Tests for the NL-to-Cypher query engine."""

from __future__ import annotations

import pytest

from src.query_engine.nl_to_cypher import NLQueryEngine, QueryResult


@pytest.fixture()
def engine() -> NLQueryEngine:
    return NLQueryEngine()


class TestCveById:
    def test_cve_id_extracted(self, engine: NLQueryEngine) -> None:
        result = engine.translate("Show me CVE-2024-12345 details")
        assert result.intent == "cve_by_id"
        assert result.parameters["cve_id"] == "CVE-2024-12345"
        assert "MATCH (c:CVE" in result.cypher

    def test_lowercase_cve_normalised(self, engine: NLQueryEngine) -> None:
        result = engine.translate("Tell me about cve-2021-44228")
        assert result.intent == "cve_by_id"
        assert result.parameters["cve_id"] == "CVE-2021-44228"

    def test_confidence_set(self, engine: NLQueryEngine) -> None:
        result = engine.translate("Show me CVE-2024-12345")
        assert result.confidence > 0.0


class TestCriticalCves:
    def test_critical_intent(self, engine: NLQueryEngine) -> None:
        result = engine.translate("List all critical CVE vulnerabilities")
        assert result.intent in ("critical_cves", "cve_by_id")

    def test_cypher_has_critical(self, engine: NLQueryEngine) -> None:
        result = engine.translate("Show critical CVE vulnerabilities")
        assert "CRITICAL" in result.cypher or "severity" in result.cypher


class TestTopCves:
    def test_top_10(self, engine: NLQueryEngine) -> None:
        result = engine.translate("Show top 10 most critical CVEs by score")
        assert result.intent == "top_cves"
        assert result.parameters["limit"] == 10

    def test_top_5(self, engine: NLQueryEngine) -> None:
        result = engine.translate("Top 5 vulnerabilities by CVSS score")
        assert result.parameters.get("limit") == 5


class TestKEV:
    def test_kev_intent(self, engine: NLQueryEngine) -> None:
        result = engine.translate("Which CVEs are in the KEV catalog?")
        assert result.intent == "kev_status"

    def test_kev_with_cve_id(self, engine: NLQueryEngine) -> None:
        result = engine.translate("Is CVE-2021-44228 in the KEV catalog?")
        assert result.intent in ("kev_status", "cve_by_id")

    def test_actively_exploited(self, engine: NLQueryEngine) -> None:
        result = engine.translate("Show actively exploited vulnerabilities")
        assert result.intent == "kev_status"


class TestVendorCves:
    def test_apache_vendor(self, engine: NLQueryEngine) -> None:
        result = engine.translate("CVEs affecting Apache software")
        assert result.intent == "cves_for_vendor"
        assert result.parameters.get("vendor") == "apache"

    def test_log4j_vendor(self, engine: NLQueryEngine) -> None:
        result = engine.translate("Vulnerabilities impacting log4j")
        assert result.intent == "cves_for_vendor"


class TestTechniques:
    def test_techniques_by_tactic(self, engine: NLQueryEngine) -> None:
        result = engine.translate("Show attack techniques for execution tactic")
        assert result.intent == "techniques_by_tactic"
        assert result.parameters.get("tactic") == "execution"

    def test_lateral_movement(self, engine: NLQueryEngine) -> None:
        result = engine.translate("List techniques for lateral movement")
        assert result.intent == "techniques_by_tactic"
        assert "lateral" in result.parameters.get("tactic", "")

    def test_techniques_for_cve(self, engine: NLQueryEngine) -> None:
        result = engine.translate("Which attack techniques exploit CVE-2021-44228?")
        assert result.intent in ("techniques_for_cve", "cve_by_id")


class TestEPSS:
    def test_epss_intent(self, engine: NLQueryEngine) -> None:
        result = engine.translate("CVEs with high EPSS exploitation probability")
        assert result.intent == "epss_high"
        assert result.parameters.get("threshold") == 0.7


class TestUnknown:
    def test_unknown_query(self, engine: NLQueryEngine) -> None:
        result = engine.translate("What is the weather like today?")
        assert result.intent == "unknown"
        assert result.confidence == 0.0
        assert "RETURN" in result.cypher

    def test_result_preserves_question(self, engine: NLQueryEngine) -> None:
        q = "How many CVEs were published last month?"
        result = engine.translate(q)
        assert result.natural_language == q


class TestQueryResult:
    def test_is_dataclass(self, engine: NLQueryEngine) -> None:
        result = engine.translate("Show CVE-2024-00001")
        assert isinstance(result, QueryResult)
        assert hasattr(result, "cypher")
        assert hasattr(result, "parameters")
        assert hasattr(result, "intent")

    def test_cypher_is_nonempty(self, engine: NLQueryEngine) -> None:
        result = engine.translate("Show CVE-2024-00001")
        assert len(result.cypher) > 0
