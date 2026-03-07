"""Tests for the NLP text enricher."""

from __future__ import annotations

import pytest

from src.nlp.enricher import EnrichmentResult, TextEnricher


@pytest.fixture()
def enricher() -> TextEnricher:
    return TextEnricher(use_spacy=False)


class TestCVEExtraction:
    def test_single_cve(self, enricher: TextEnricher) -> None:
        result = enricher.enrich("This affects CVE-2024-12345.")
        assert "CVE-2024-12345" in result.cve_refs

    def test_multiple_cves(self, enricher: TextEnricher) -> None:
        result = enricher.enrich("See CVE-2021-44228 and CVE-2022-0001 for details.")
        assert len(result.cve_refs) == 2
        assert "CVE-2021-44228" in result.cve_refs
        assert "CVE-2022-0001" in result.cve_refs

    def test_case_insensitive(self, enricher: TextEnricher) -> None:
        result = enricher.enrich("Affects cve-2024-99999.")
        assert "CVE-2024-99999" in result.cve_refs

    def test_no_cve(self, enricher: TextEnricher) -> None:
        result = enricher.enrich("No CVE here.")
        assert result.cve_refs == []


class TestCWEExtraction:
    def test_single_cwe(self, enricher: TextEnricher) -> None:
        result = enricher.enrich("Classified as CWE-79.")
        assert "CWE-79" in result.cwe_refs

    def test_multiple_cwes(self, enricher: TextEnricher) -> None:
        result = enricher.enrich("This maps to CWE-89 and CWE-190.")
        assert "CWE-89" in result.cwe_refs
        assert "CWE-190" in result.cwe_refs

    def test_no_cwe(self, enricher: TextEnricher) -> None:
        result = enricher.enrich("No weakness listed.")
        assert result.cwe_refs == []


class TestVulnTypeExtraction:
    def test_rce_detection(self, enricher: TextEnricher) -> None:
        result = enricher.enrich("This allows remote code execution via crafted input.")
        assert "remote_code_execution" in result.vuln_types

    def test_rce_abbreviation(self, enricher: TextEnricher) -> None:
        result = enricher.enrich("Unauthenticated RCE in the login handler.")
        assert "remote_code_execution" in result.vuln_types

    def test_sql_injection(self, enricher: TextEnricher) -> None:
        result = enricher.enrich("SQL injection via the search parameter.")
        assert "sql_injection" in result.vuln_types

    def test_xss(self, enricher: TextEnricher) -> None:
        result = enricher.enrich("Cross-site scripting in the comment field.")
        assert "xss" in result.vuln_types

    def test_buffer_overflow(self, enricher: TextEnricher) -> None:
        result = enricher.enrich("Stack overflow in the parser.")
        assert "buffer_overflow" in result.vuln_types

    def test_privilege_escalation(self, enricher: TextEnricher) -> None:
        result = enricher.enrich("Local privilege escalation to root.")
        assert "privilege_escalation" in result.vuln_types

    def test_dos(self, enricher: TextEnricher) -> None:
        result = enricher.enrich("Denial-of-service via crafted packets.")
        assert "denial_of_service" in result.vuln_types

    def test_ssrf(self, enricher: TextEnricher) -> None:
        result = enricher.enrich("SSRF in the URL fetch endpoint.")
        assert "ssrf" in result.vuln_types

    def test_xxe(self, enricher: TextEnricher) -> None:
        result = enricher.enrich("XML external entity (XXE) in the XML parser.")
        assert "xxe" in result.vuln_types

    def test_deserialization(self, enricher: TextEnricher) -> None:
        result = enricher.enrich("Unsafe deserialization of user-supplied data.")
        assert "deserialization" in result.vuln_types

    def test_path_traversal(self, enricher: TextEnricher) -> None:
        result = enricher.enrich("Path traversal allows reading arbitrary files.")
        assert "path_traversal" in result.vuln_types

    def test_multiple_types(self, enricher: TextEnricher) -> None:
        result = enricher.enrich("XSS and SQL injection both present.")
        assert "xss" in result.vuln_types
        assert "sql_injection" in result.vuln_types

    def test_benign_text_no_types(self, enricher: TextEnricher) -> None:
        result = enricher.enrich("This is a minor cosmetic bug.")
        assert result.vuln_types == []


class TestVendorExtraction:
    def test_known_vendor(self, enricher: TextEnricher) -> None:
        result = enricher.enrich("A vulnerability in Apache HTTP Server.")
        assert any("Apache" in v for v in result.vendors)

    def test_log4j_vendor(self, enricher: TextEnricher) -> None:
        result = enricher.enrich("Log4j remote code execution (CVE-2021-44228).")
        assert any("Log4j" in v for v in result.vendors)

    def test_no_vendor(self, enricher: TextEnricher) -> None:
        result = enricher.enrich("A generic vulnerability with no named vendor.")
        assert result.vendors == []

    def test_duplicate_vendor_not_repeated(self, enricher: TextEnricher) -> None:
        result = enricher.enrich("Apache HTTP Server and Apache Tomcat both affected.")
        apache_count = sum(1 for v in result.vendors if "apache" in v.lower())
        assert apache_count == 1


class TestEntities:
    def test_entities_populated(self, enricher: TextEnricher) -> None:
        result = enricher.enrich("Apache RCE via CVE-2024-12345 (CWE-79).")
        assert len(result.entities) >= 2

    def test_entity_positions(self, enricher: TextEnricher) -> None:
        text = "CVE-2024-12345 is critical."
        result = enricher.enrich(text)
        cve_entity = next(e for e in result.entities if e.entity_type == "cve_ref")
        assert text[cve_entity.start : cve_entity.end] == "CVE-2024-12345"


class TestEnrichmentResult:
    def test_empty_text(self, enricher: TextEnricher) -> None:
        result = enricher.enrich("")
        assert isinstance(result, EnrichmentResult)
        assert result.cve_refs == []
        assert result.cwe_refs == []
        assert result.vendors == []
        assert result.vuln_types == []

    def test_result_text_preserved(self, enricher: TextEnricher) -> None:
        text = "Test description."
        result = enricher.enrich(text)
        assert result.text == text
