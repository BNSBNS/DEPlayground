"""Shared test fixtures for TIKG."""

from __future__ import annotations

import datetime

import pytest

from src.models import CVE, CWE, AttackTechnique, CPEMatch, CVSSScore, KEVEntry, Software


@pytest.fixture()
def cvss_v3() -> CVSSScore:
    return CVSSScore(
        version="3.1",
        base_score=9.8,
        severity="CRITICAL",
        vector_string="CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
    )


@pytest.fixture()
def cvss_v2() -> CVSSScore:
    return CVSSScore(
        version="2.0",
        base_score=7.5,
        severity="HIGH",
        vector_string="AV:N/AC:L/Au:N/C:P/I:P/A:P",
    )


@pytest.fixture()
def sample_cve(cvss_v3: CVSSScore) -> CVE:
    return CVE(
        cve_id="CVE-2024-12345",
        description="A critical remote code execution vulnerability.",
        published=datetime.datetime(2024, 1, 15, tzinfo=datetime.UTC),
        last_modified=datetime.datetime(2024, 2, 1, tzinfo=datetime.UTC),
        cvss_v3=cvss_v3,
        cwe_ids=["CWE-79", "CWE-89"],
        cpe_matches=[
            CPEMatch(
                cpe_name="cpe:2.3:a:vendor:product:1.0:*:*:*:*:*:*:*",
                version_end_excluding="1.1",
            )
        ],
        reference_urls=["https://example.com/advisory/2024-001"],
        epss_score=0.92,
    )


@pytest.fixture()
def cve_no_cvss() -> CVE:
    return CVE(
        cve_id="CVE-2024-99999",
        description="A vulnerability with no CVSS score yet.",
        published=datetime.datetime(2024, 3, 1, tzinfo=datetime.UTC),
        last_modified=datetime.datetime(2024, 3, 1, tzinfo=datetime.UTC),
    )


@pytest.fixture()
def sample_technique() -> AttackTechnique:
    return AttackTechnique(
        technique_id="T1059",
        name="Command and Scripting Interpreter",
        description="Adversaries may abuse command and script interpreters to execute commands.",
        tactic="execution",
        sub_techniques=["T1059.001", "T1059.003"],
        detection="Monitor process creation events for shells.",
        platforms=["Windows", "Linux", "macOS"],
    )


@pytest.fixture()
def sample_kev() -> KEVEntry:
    return KEVEntry(
        cve_id="CVE-2024-12345",
        vendor_project="Example Corp",
        product="Example Product",
        vulnerability_name="Example RCE",
        date_added=datetime.datetime(2024, 2, 10, tzinfo=datetime.UTC),
        short_description="Remote code execution in Example Product.",
        required_action="Apply vendor patch immediately.",
        due_date=datetime.datetime(2024, 2, 24, tzinfo=datetime.UTC),
    )


@pytest.fixture()
def sample_software() -> Software:
    return Software(vendor="apache", product="log4j", version="2.14.0")


@pytest.fixture()
def sample_cwe() -> CWE:
    return CWE(
        cwe_id="CWE-79",
        name="Cross-site Scripting",
        description="Improper neutralization of input during web page generation.",
    )
