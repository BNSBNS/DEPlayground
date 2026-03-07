"""CISA KEV client — fetches the Known Exploited Vulnerabilities catalog."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import httpx

from src.models import KEVEntry

logger = logging.getLogger(__name__)

_KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
_DATE_FORMAT = "%Y-%m-%d"


def _parse_kev_entry(item: dict[str, Any]) -> KEVEntry | None:
    """Parse a single KEV catalog entry dict."""
    try:
        date_added = datetime.strptime(str(item["dateAdded"]), _DATE_FORMAT)
        due_date_raw: str | None = item.get("dueDate")
        due_date = datetime.strptime(due_date_raw, _DATE_FORMAT) if due_date_raw else None
        return KEVEntry(
            cve_id=str(item["cveID"]),
            vendor_project=str(item["vendorProject"]),
            product=str(item["product"]),
            vulnerability_name=str(item["vulnerabilityName"]),
            date_added=date_added,
            short_description=str(item["shortDescription"]),
            required_action=str(item["requiredAction"]),
            due_date=due_date,
        )
    except (KeyError, ValueError) as exc:
        logger.warning("Skipping malformed KEV entry: %s", exc)
        return None


class KEVClient:
    """Async client for the CISA KEV catalog."""

    def __init__(self, url: str = _KEV_URL) -> None:
        self._url = url
        self._client = httpx.AsyncClient(timeout=30.0)

    async def __aenter__(self) -> KEVClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self._client.aclose()

    async def fetch_all(self) -> list[KEVEntry]:
        """Download the KEV catalog and return parsed entries."""
        resp = await self._client.get(self._url)
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        vulnerabilities: list[dict[str, Any]] = data.get("vulnerabilities", [])

        entries: list[KEVEntry] = []
        for item in vulnerabilities:
            entry = _parse_kev_entry(item)
            if entry is not None:
                entries.append(entry)

        logger.info("CISA KEV: loaded %d entries", len(entries))
        return entries
