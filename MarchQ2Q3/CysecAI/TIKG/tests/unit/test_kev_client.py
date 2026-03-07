"""Tests for the CISA KEV client."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.ingestion.kev_client import KEVClient, _parse_kev_entry
from src.models import KEVEntry


def _make_kev_item(
    cve_id: str = "CVE-2024-12345",
    vendor: str = "Example Corp",
    product: str = "Widget",
    name: str = "Widget RCE",
    date_added: str = "2024-01-15",
    description: str = "Remote code execution.",
    action: str = "Apply patch.",
    due_date: str | None = "2024-01-29",
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "cveID": cve_id,
        "vendorProject": vendor,
        "product": product,
        "vulnerabilityName": name,
        "dateAdded": date_added,
        "shortDescription": description,
        "requiredAction": action,
    }
    if due_date is not None:
        item["dueDate"] = due_date
    return item


def _make_kev_response(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "title": "CISA KEV Catalog",
        "catalogVersion": "2024.01.15",
        "vulnerabilities": items,
    }


class TestParseKevEntry:
    def test_valid_entry(self) -> None:
        item = _make_kev_item()
        entry = _parse_kev_entry(item)
        assert entry is not None
        assert entry.cve_id == "CVE-2024-12345"
        assert entry.vendor_project == "Example Corp"
        assert entry.due_date is not None
        assert entry.due_date.year == 2024

    def test_no_due_date(self) -> None:
        item = _make_kev_item(due_date=None)
        entry = _parse_kev_entry(item)
        assert entry is not None
        assert entry.due_date is None

    def test_date_parsed_correctly(self) -> None:
        item = _make_kev_item(date_added="2023-11-05")
        entry = _parse_kev_entry(item)
        assert entry is not None
        assert entry.date_added.month == 11
        assert entry.date_added.day == 5

    def test_malformed_missing_key_returns_none(self) -> None:
        item = {"cveID": "CVE-2024-00000"}  # missing required fields
        result = _parse_kev_entry(item)
        assert result is None

    def test_malformed_date_returns_none(self) -> None:
        item = _make_kev_item(date_added="not-a-date")
        result = _parse_kev_entry(item)
        assert result is None


class TestKEVClient:
    @pytest.mark.asyncio
    async def test_fetch_all_returns_entries(self) -> None:
        items = [_make_kev_item("CVE-2024-00001"), _make_kev_item("CVE-2024-00002")]
        response_data = _make_kev_response(items)
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value=response_data)

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            async with KEVClient() as client:
                entries = await client.fetch_all()

        assert len(entries) == 2
        assert all(isinstance(e, KEVEntry) for e in entries)
        ids = {e.cve_id for e in entries}
        assert "CVE-2024-00001" in ids

    @pytest.mark.asyncio
    async def test_fetch_all_skips_malformed(self) -> None:
        items = [
            _make_kev_item("CVE-2024-GOOD"),
            {"cveID": "CVE-2024-BAD"},  # malformed
        ]
        response_data = _make_kev_response(items)
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value=response_data)

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            async with KEVClient() as client:
                entries = await client.fetch_all()

        assert len(entries) == 1
        assert entries[0].cve_id == "CVE-2024-GOOD"

    @pytest.mark.asyncio
    async def test_fetch_all_empty_catalog(self) -> None:
        response_data = _make_kev_response([])
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value=response_data)

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            async with KEVClient() as client:
                entries = await client.fetch_all()

        assert entries == []
