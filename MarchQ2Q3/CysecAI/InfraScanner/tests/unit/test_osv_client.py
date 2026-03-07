"""Tests for OSV client with mocked HTTP responses."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from src.models import Dependency, Ecosystem, Severity
from src.vuln_db.osv_client import OSVClient, _parse_osv_vuln


class TestParseOsvVuln:
    def test_cve_alias_preferred(self) -> None:
        raw: dict[str, Any] = {
            "id": "GHSA-j8r2-6x86-q33q",
            "aliases": ["CVE-2023-32681"],
            "summary": "Test vulnerability",
            "severity": [],
        }
        vuln = _parse_osv_vuln(raw)
        assert vuln.vuln_id == "CVE-2023-32681"

    def test_ghsa_id_fallback(self) -> None:
        raw: dict[str, Any] = {
            "id": "GHSA-j8r2-6x86-q33q",
            "aliases": [],
            "summary": "Test",
            "severity": [],
        }
        vuln = _parse_osv_vuln(raw)
        assert vuln.vuln_id == "GHSA-j8r2-6x86-q33q"

    def test_severity_parsed(self) -> None:
        raw: dict[str, Any] = {
            "id": "CVE-2023-0001",
            "aliases": [],
            "summary": "High severity vuln",
            "severity": [{"type": "CVSS_V3", "score": "8.1"}],
        }
        vuln = _parse_osv_vuln(raw)
        assert vuln.severity == Severity.HIGH
        assert vuln.cvss_score is not None
        assert vuln.cvss_score == 8.1

    def test_reference_urls(self) -> None:
        raw: dict[str, Any] = {
            "id": "CVE-2023-0001",
            "aliases": [],
            "summary": "",
            "severity": [],
            "references": [{"url": "https://example.com/cve"}],
        }
        vuln = _parse_osv_vuln(raw)
        assert len(vuln.reference_urls) == 1

    def test_affected_versions_extracted(self) -> None:
        raw: dict[str, Any] = {
            "id": "CVE-2023-0001",
            "aliases": [],
            "summary": "",
            "severity": [],
            "affected": [
                {
                    "ranges": [
                        {
                            "type": "ECOSYSTEM",
                            "events": [{"introduced": "0"}, {"fixed": "2.31.0"}],
                        }
                    ]
                }
            ],
        }
        vuln = _parse_osv_vuln(raw)
        assert any("2.31.0" in v for v in vuln.affected_versions)


class TestOSVClientBatch:
    async def test_returns_empty_for_no_versioned_deps(self) -> None:
        client = OSVClient()
        dep = Dependency(name="requests", ecosystem=Ecosystem.PYPI)  # no version
        result = await client.query_batch([dep])
        assert result == {}

    async def test_maps_results_by_index(self, mock_osv_response: dict[str, Any]) -> None:
        client = OSVClient()
        deps = [
            Dependency(name="requests", version="2.18.4", ecosystem=Ecosystem.PYPI),
        ]

        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_osv_response

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
            result = await client.query_batch(deps)

        assert 0 in result
        assert len(result[0]) == 1
        assert result[0][0].vuln_id == "CVE-2023-32681"

    async def test_docker_deps_skipped(self) -> None:
        client = OSVClient()
        deps = [
            Dependency(name="ubuntu", version="22.04", ecosystem=Ecosystem.DOCKER),
        ]
        result = await client.query_batch(deps)
        assert result == {}

    async def test_empty_dep_list(self) -> None:
        result = await OSVClient().query_batch([])
        assert result == {}
