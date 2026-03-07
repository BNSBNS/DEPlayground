"""Tests for the NVD 2.0 API client."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config import NVDSettings
from src.ingestion.nvd_client import NVDClient, _parse_cve_item, _parse_nvd_date
from src.models import CVE

# ---------------------------------------------------------------------------
# Helpers — build minimal NVD response payloads
# ---------------------------------------------------------------------------


def _make_nvd_cve(
    cve_id: str = "CVE-2024-12345",
    description: str = "Test vuln",
    severity: str = "HIGH",
    base_score: float = 7.5,
    cwe: str | None = "CWE-79",
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "cve": {
            "id": cve_id,
            "published": "2024-01-15T12:00:00.000",
            "lastModified": "2024-02-01T08:30:00.000",
            "descriptions": [{"lang": "en", "value": description}],
            "metrics": {
                "cvssMetricV31": [
                    {
                        "cvssData": {
                            "version": "3.1",
                            "baseScore": base_score,
                            "baseSeverity": severity,
                            "vectorString": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N",
                        }
                    }
                ]
            },
            "weaknesses": ([{"description": [{"lang": "en", "value": cwe}]}] if cwe else []),
            "configurations": [],
            "references": [{"url": "https://example.com/advisory"}],
        }
    }
    return item


def _make_nvd_response(items: list[dict[str, Any]], total: int | None = None) -> dict[str, Any]:
    return {
        "totalResults": total if total is not None else len(items),
        "resultsPerPage": len(items),
        "startIndex": 0,
        "vulnerabilities": items,
    }


# ---------------------------------------------------------------------------
# _parse_nvd_date
# ---------------------------------------------------------------------------


class TestParseNvdDate:
    def test_with_milliseconds(self) -> None:
        dt = _parse_nvd_date("2024-01-15T12:00:00.000")
        assert dt.year == 2024
        assert dt.month == 1
        assert dt.day == 15

    def test_without_milliseconds(self) -> None:
        dt = _parse_nvd_date("2024-06-01T08:30:00")
        assert dt.year == 2024
        assert dt.hour == 8

    def test_strips_timezone_offset(self) -> None:
        dt = _parse_nvd_date("2024-01-01T00:00:00.000+0000")
        assert dt.year == 2024

    def test_invalid_format(self) -> None:
        with pytest.raises(ValueError, match="Unrecognised"):
            _parse_nvd_date("not-a-date")


# ---------------------------------------------------------------------------
# _parse_cve_item
# ---------------------------------------------------------------------------


class TestParseCveItem:
    def test_basic_fields(self) -> None:
        item = _make_nvd_cve("CVE-2024-00001", "A test vulnerability")
        cve = _parse_cve_item(item)
        assert cve.cve_id == "CVE-2024-00001"
        assert cve.description == "A test vulnerability"
        assert isinstance(cve.published, datetime)

    def test_cvss_v3_parsed(self) -> None:
        item = _make_nvd_cve(base_score=9.8, severity="CRITICAL")
        cve = _parse_cve_item(item)
        assert cve.cvss_v3 is not None
        assert cve.cvss_v3.base_score == pytest.approx(9.8)
        assert cve.cvss_v3.severity == "CRITICAL"

    def test_cwe_extracted(self) -> None:
        item = _make_nvd_cve(cwe="CWE-89")
        cve = _parse_cve_item(item)
        assert "CWE-89" in cve.cwe_ids

    def test_no_cwe(self) -> None:
        item = _make_nvd_cve(cwe=None)
        cve = _parse_cve_item(item)
        assert cve.cwe_ids == []

    def test_reference_urls(self) -> None:
        item = _make_nvd_cve()
        cve = _parse_cve_item(item)
        assert len(cve.reference_urls) == 1
        assert "example.com" in cve.reference_urls[0]

    def test_english_description_preferred(self) -> None:
        item = _make_nvd_cve()
        item["cve"]["descriptions"] = [
            {"lang": "es", "value": "Vulnerabilidad de prueba"},
            {"lang": "en", "value": "English description"},
        ]
        cve = _parse_cve_item(item)
        assert cve.description == "English description"

    def test_cvss_v2_parsed(self) -> None:
        item = _make_nvd_cve()
        item["cve"]["metrics"] = {
            "cvssMetricV2": [
                {
                    "baseSeverity": "HIGH",
                    "cvssData": {
                        "baseScore": 7.5,
                        "vectorString": "AV:N/AC:L/Au:N/C:P/I:P/A:P",
                    },
                }
            ]
        }
        cve = _parse_cve_item(item)
        assert cve.cvss_v2 is not None
        assert cve.cvss_v2.base_score == pytest.approx(7.5)
        assert cve.cvss_v3 is None


# ---------------------------------------------------------------------------
# NVDClient (mocked HTTP)
# ---------------------------------------------------------------------------


class TestNVDClient:
    @pytest.mark.asyncio
    async def test_fetch_page_returns_dict(self) -> None:
        response_data = _make_nvd_response([_make_nvd_cve()])
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value=response_data)

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            async with NVDClient() as client:
                result = await client.fetch_page(start_index=0)

        assert "vulnerabilities" in result
        assert result["totalResults"] == 1

    @pytest.mark.asyncio
    async def test_fetch_all_single_page(self) -> None:
        items = [_make_nvd_cve("CVE-2024-00001"), _make_nvd_cve("CVE-2024-00002")]
        response_data = _make_nvd_response(items)
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value=response_data)

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            async with NVDClient() as client:
                cves = await client.fetch_all()

        assert len(cves) == 2
        assert all(isinstance(c, CVE) for c in cves)
        ids = {c.cve_id for c in cves}
        assert "CVE-2024-00001" in ids
        assert "CVE-2024-00002" in ids

    @pytest.mark.asyncio
    async def test_fetch_all_pagination(self) -> None:
        page1 = _make_nvd_response([_make_nvd_cve("CVE-2024-00001")], total=2)
        page2_items = [_make_nvd_cve("CVE-2024-00002")]
        page2 = {
            "totalResults": 2,
            "resultsPerPage": 1,
            "startIndex": 1,
            "vulnerabilities": page2_items,
        }

        responses = [page1, page2]
        call_count = 0

        async def mock_get(*_: Any, **__: Any) -> MagicMock:
            nonlocal call_count
            data = responses[call_count % len(responses)]
            call_count += 1
            mock_resp = MagicMock()
            mock_resp.raise_for_status = MagicMock()
            mock_resp.json = MagicMock(return_value=data)
            return mock_resp

        with (
            patch("httpx.AsyncClient.get", side_effect=mock_get),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            async with NVDClient() as client:
                client._settings.results_per_page = 1
                cves = await client.fetch_all()

        assert len(cves) == 2

    @pytest.mark.asyncio
    async def test_fetch_all_skips_malformed(self) -> None:
        items = [
            _make_nvd_cve("CVE-2024-GOOD"),
            {"cve": {}},  # malformed — missing required fields
        ]
        response_data = {
            "totalResults": 2,
            "resultsPerPage": 2,
            "startIndex": 0,
            "vulnerabilities": items,
        }
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value=response_data)

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            async with NVDClient() as client:
                cves = await client.fetch_all()

        assert len(cves) == 1
        assert cves[0].cve_id == "CVE-2024-GOOD"

    @pytest.mark.asyncio
    async def test_api_key_added_to_headers(self) -> None:
        settings = NVDSettings(api_key="my-test-key")
        async with NVDClient(settings=settings) as client:
            assert client._client.headers.get("apiKey") == "my-test-key"

    @pytest.mark.asyncio
    async def test_fetch_all_empty_response(self) -> None:
        response_data = _make_nvd_response([])
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value=response_data)

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            async with NVDClient() as client:
                cves = await client.fetch_all()

        assert cves == []

    def test_json_serialization(self) -> None:
        """Ensure the mock NVD response payload is valid JSON."""
        item = _make_nvd_cve()
        payload = _make_nvd_response([item])
        assert json.dumps(payload)  # no exception
