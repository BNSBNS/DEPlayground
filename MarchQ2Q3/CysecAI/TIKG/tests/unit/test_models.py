"""Tests for TIKG Pydantic models."""

from __future__ import annotations

import datetime

import pytest
from pydantic import ValidationError

from src.models import CVE, CWE, AttackTechnique, CPEMatch, CVSSScore, KEVEntry, Software

_UTC = datetime.UTC
_DT = datetime.datetime


class TestCVSSScore:
    def test_valid(self) -> None:
        s = CVSSScore(version="3.1", base_score=9.8, severity="CRITICAL")
        assert s.version == "3.1"
        assert s.base_score == 9.8
        assert s.vector_string == ""

    def test_with_vector(self) -> None:
        s = CVSSScore(
            version="2.0",
            base_score=5.0,
            severity="MEDIUM",
            vector_string="AV:N/AC:L/Au:N/C:P/I:N/A:N",
        )
        assert s.vector_string.startswith("AV:")

    def test_missing_required(self) -> None:
        with pytest.raises(ValidationError):
            CVSSScore(version="3.1", base_score=9.8)  # type: ignore[call-arg]


class TestCPEMatch:
    def test_defaults(self) -> None:
        c = CPEMatch(cpe_name="cpe:2.3:a:vendor:product:*:*:*:*:*:*:*:*")
        assert c.vulnerable is True
        assert c.version_start_including is None
        assert c.version_end_excluding is None

    def test_with_version_range(self) -> None:
        c = CPEMatch(
            cpe_name="cpe:2.3:a:vendor:product:*",
            version_start_including="1.0",
            version_end_excluding="1.5",
        )
        assert c.version_start_including == "1.0"
        assert c.version_end_excluding == "1.5"


class TestCVE:
    def test_severity_v3_preferred(self, sample_cve: CVE) -> None:
        assert sample_cve.severity == "CRITICAL"

    def test_severity_falls_back_to_v2(self, cvss_v2: CVSSScore) -> None:
        cve = CVE(
            cve_id="CVE-2024-00001",
            description="Test",
            published=_DT(2024, 1, 1, tzinfo=_UTC),
            last_modified=_DT(2024, 1, 1, tzinfo=_UTC),
            cvss_v2=cvss_v2,
        )
        assert cve.severity == "HIGH"

    def test_severity_unknown_when_no_cvss(self, cve_no_cvss: CVE) -> None:
        assert cve_no_cvss.severity == "UNKNOWN"

    def test_base_score_v3_preferred(self, sample_cve: CVE) -> None:
        assert sample_cve.base_score == 9.8

    def test_base_score_falls_back_to_v2(self, cvss_v2: CVSSScore) -> None:
        cve = CVE(
            cve_id="CVE-2024-00002",
            description="Test",
            published=_DT(2024, 1, 1, tzinfo=_UTC),
            last_modified=_DT(2024, 1, 1, tzinfo=_UTC),
            cvss_v2=cvss_v2,
        )
        assert cve.base_score == 7.5

    def test_base_score_none_when_no_cvss(self, cve_no_cvss: CVE) -> None:
        assert cve_no_cvss.base_score is None

    def test_defaults(self) -> None:
        cve = CVE(
            cve_id="CVE-2024-11111",
            description="Minimal",
            published=_DT(2024, 1, 1, tzinfo=_UTC),
            last_modified=_DT(2024, 1, 1, tzinfo=_UTC),
        )
        assert cve.cwe_ids == []
        assert cve.cpe_matches == []
        assert cve.reference_urls == []
        assert cve.epss_score is None
        assert cve.cvss_v3 is None
        assert cve.cvss_v2 is None

    def test_cwe_ids_populated(self, sample_cve: CVE) -> None:
        assert "CWE-79" in sample_cve.cwe_ids
        assert "CWE-89" in sample_cve.cwe_ids

    def test_cpe_matches_populated(self, sample_cve: CVE) -> None:
        assert len(sample_cve.cpe_matches) == 1
        assert sample_cve.cpe_matches[0].version_end_excluding == "1.1"

    def test_epss_score(self, sample_cve: CVE) -> None:
        assert sample_cve.epss_score == pytest.approx(0.92)

    def test_invalid_missing_required(self) -> None:
        with pytest.raises(ValidationError):
            CVE(cve_id="CVE-2024-0")  # type: ignore[call-arg]


class TestAttackTechnique:
    def test_valid(self, sample_technique: AttackTechnique) -> None:
        assert sample_technique.technique_id == "T1059"
        assert sample_technique.tactic == "execution"
        assert len(sample_technique.sub_techniques) == 2
        assert len(sample_technique.platforms) == 3

    def test_defaults(self) -> None:
        t = AttackTechnique(
            technique_id="T1001",
            name="Data Obfuscation",
            description="Adversaries may obfuscate data.",
            tactic="command-and-control",
        )
        assert t.sub_techniques == []
        assert t.platforms == []
        assert t.detection is None


class TestKEVEntry:
    def test_valid(self, sample_kev: KEVEntry) -> None:
        assert sample_kev.cve_id == "CVE-2024-12345"
        assert sample_kev.due_date is not None

    def test_no_due_date(self) -> None:
        kev = KEVEntry(
            cve_id="CVE-2024-00000",
            vendor_project="Acme",
            product="Widget",
            vulnerability_name="Widget RCE",
            date_added=_DT(2024, 1, 1, tzinfo=_UTC),
            short_description="Remote code execution.",
            required_action="Update immediately.",
        )
        assert kev.due_date is None


class TestSoftware:
    def test_node_id_with_version(self, sample_software: Software) -> None:
        assert sample_software.node_id == "apache:log4j:2.14.0"

    def test_node_id_without_version(self) -> None:
        s = Software(vendor="microsoft", product="exchange")
        assert s.node_id == "microsoft:exchange:*"

    def test_version_none(self) -> None:
        s = Software(vendor="vendor", product="product")
        assert s.version is None


class TestCWE:
    def test_valid(self, sample_cwe: CWE) -> None:
        assert sample_cwe.cwe_id == "CWE-79"
        assert "Scripting" in sample_cwe.name

    def test_defaults(self) -> None:
        c = CWE(cwe_id="CWE-999")
        assert c.name == ""
        assert c.description == ""
