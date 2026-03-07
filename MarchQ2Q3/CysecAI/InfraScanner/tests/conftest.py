"""Shared fixtures for InfraScanner tests."""

from __future__ import annotations

import pytest

from src.models import Dependency, Ecosystem, Severity, Vulnerability


@pytest.fixture()
def sample_pypi_dep() -> Dependency:
    return Dependency(
        name="requests",
        version="2.18.4",
        ecosystem=Ecosystem.PYPI,
        source_file="requirements.txt",
    )


@pytest.fixture()
def sample_npm_dep() -> Dependency:
    return Dependency(
        name="lodash",
        version="4.17.11",
        ecosystem=Ecosystem.NPM,
        source_file="package.json",
    )


@pytest.fixture()
def sample_go_dep() -> Dependency:
    return Dependency(
        name="golang.org/x/net",
        version="0.1.0",
        ecosystem=Ecosystem.GO,
        source_file="go.mod",
    )


@pytest.fixture()
def sample_vulnerability() -> Vulnerability:
    return Vulnerability(
        vuln_id="CVE-2023-12345",
        description="Example test vulnerability",
        cvss_score=7.5,
        severity=Severity.HIGH,
        epss_score=0.05,
    )


@pytest.fixture()
def mock_osv_response() -> dict[str, object]:
    """Minimal OSV batch response with one vulnerability."""
    return {
        "results": [
            {
                "vulns": [
                    {
                        "id": "GHSA-j8r2-6x86-q33q",
                        "aliases": ["CVE-2023-32681"],
                        "summary": "Unintended leak of Proxy-Authorization header",
                        "severity": [{"type": "CVSS_V3", "score": "7.2"}],
                        "affected": [
                            {
                                "package": {"name": "requests", "ecosystem": "PyPI"},
                                "ranges": [
                                    {
                                        "type": "ECOSYSTEM",
                                        "events": [
                                            {"introduced": "0"},
                                            {"fixed": "2.31.0"},
                                        ],
                                    }
                                ],
                            }
                        ],
                        "references": [
                            {
                                "url": "https://github.com/psf/requests/security/advisories/GHSA-j8r2-6x86-q33q"
                            }
                        ],
                    }
                ]
            }
        ]
    }
