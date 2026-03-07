"""NVD 2.0 API client — paginated CVE fetching with rate limiting."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

import httpx

from src.config import NVDSettings
from src.models import CVE, CPEMatch, CVSSScore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# NVD API response parsing helpers
# ---------------------------------------------------------------------------

_NVD_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S.%f"
_NVD_DATE_FORMAT_SHORT = "%Y-%m-%dT%H:%M:%S"


def _parse_nvd_date(raw: str) -> datetime:
    """Parse NVD date strings (may include timezone offset)."""
    # Strip trailing timezone like '+0000'
    clean = raw.split("+", maxsplit=1)[0].rstrip("Z").strip()
    for fmt in (_NVD_DATE_FORMAT, _NVD_DATE_FORMAT_SHORT):
        try:
            return datetime.strptime(clean, fmt)
        except ValueError:
            continue
    msg = f"Unrecognised NVD date format: {raw!r}"
    raise ValueError(msg)


def _parse_cvss_v3(metrics: dict[str, Any]) -> CVSSScore | None:
    entries: list[dict[str, Any]] = metrics.get("cvssMetricV31", []) or metrics.get(
        "cvssMetricV30", []
    )
    if not entries:
        return None
    d = entries[0]["cvssData"]
    return CVSSScore(
        version=str(d.get("version", "3.x")),
        base_score=float(d["baseScore"]),
        severity=str(d.get("baseSeverity", "UNKNOWN")).upper(),
        vector_string=str(d.get("vectorString", "")),
    )


def _parse_cvss_v2(metrics: dict[str, Any]) -> CVSSScore | None:
    entries: list[dict[str, Any]] = metrics.get("cvssMetricV2", [])
    if not entries:
        return None
    d = entries[0]["cvssData"]
    return CVSSScore(
        version="2.0",
        base_score=float(d["baseScore"]),
        severity=str(entries[0].get("baseSeverity", "UNKNOWN")).upper(),
        vector_string=str(d.get("vectorString", "")),
    )


def _parse_cpe_matches(config: list[dict[str, Any]]) -> list[CPEMatch]:
    matches: list[CPEMatch] = []
    for node in config:
        for m in node.get("cpeMatch", []):
            matches.append(
                CPEMatch(
                    cpe_name=str(m.get("criteria", "")),
                    vulnerable=bool(m.get("vulnerable", True)),
                    version_start_including=m.get("versionStartIncluding"),
                    version_end_excluding=m.get("versionEndExcluding"),
                )
            )
        for child in node.get("children", []):
            matches.extend(_parse_cpe_matches([child]))
    return matches


def _parse_cve_item(item: dict[str, Any]) -> CVE:
    """Parse a single NVD CVE item dict into a CVE model."""
    cve_data: dict[str, Any] = item["cve"]
    cve_id: str = cve_data["id"]

    descriptions: list[dict[str, Any]] = cve_data.get("descriptions", [])
    description = next(
        (d["value"] for d in descriptions if d.get("lang") == "en"),
        "",
    )

    metrics: dict[str, Any] = cve_data.get("metrics", {})
    weaknesses: list[dict[str, Any]] = cve_data.get("weaknesses", [])
    cwe_ids: list[str] = []
    for w in weaknesses:
        for desc in w.get("description", []):
            val = str(desc.get("value", ""))
            if val.startswith("CWE-"):
                cwe_ids.append(val)

    configs: list[dict[str, Any]] = cve_data.get("configurations", [])
    cpe_matches = _parse_cpe_matches(configs)

    references: list[dict[str, Any]] = cve_data.get("references", [])
    reference_urls = [str(r["url"]) for r in references if r.get("url")]

    return CVE(
        cve_id=cve_id,
        description=description,
        published=_parse_nvd_date(str(cve_data["published"])),
        last_modified=_parse_nvd_date(str(cve_data["lastModified"])),
        cvss_v3=_parse_cvss_v3(metrics),
        cvss_v2=_parse_cvss_v2(metrics),
        cwe_ids=cwe_ids,
        cpe_matches=cpe_matches,
        reference_urls=reference_urls,
    )


# ---------------------------------------------------------------------------
# NVD async client
# ---------------------------------------------------------------------------


class NVDClient:
    """Async HTTP client for the NVD 2.0 CVE API."""

    BASE_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"

    def __init__(self, settings: NVDSettings | None = None) -> None:
        self._settings = settings or NVDSettings()
        headers: dict[str, str] = {"Accept": "application/json"}
        if self._settings.api_key:
            headers["apiKey"] = self._settings.api_key
        self._client = httpx.AsyncClient(headers=headers, timeout=30.0)

    async def __aenter__(self) -> NVDClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self._client.aclose()

    async def fetch_page(
        self,
        start_index: int = 0,
        results_per_page: int | None = None,
        *,
        pub_start_date: datetime | None = None,
        pub_end_date: datetime | None = None,
    ) -> dict[str, Any]:
        """Fetch a single page of CVEs."""
        rpp = results_per_page or self._settings.results_per_page
        params: dict[str, str | int] = {
            "startIndex": start_index,
            "resultsPerPage": rpp,
        }
        if pub_start_date:
            params["pubStartDate"] = pub_start_date.strftime("%Y-%m-%dT%H:%M:%S.000")
        if pub_end_date:
            params["pubEndDate"] = pub_end_date.strftime("%Y-%m-%dT%H:%M:%S.000")

        resp = await self._client.get(self._settings.base_url, params=params)
        resp.raise_for_status()
        return dict(resp.json())

    async def fetch_all(
        self,
        *,
        pub_start_date: datetime | None = None,
        pub_end_date: datetime | None = None,
    ) -> list[CVE]:
        """Fetch all CVE pages and return parsed CVE models."""
        cves: list[CVE] = []
        start_index = 0
        rpp = self._settings.results_per_page

        while True:
            data = await self.fetch_page(
                start_index=start_index,
                results_per_page=rpp,
                pub_start_date=pub_start_date,
                pub_end_date=pub_end_date,
            )
            total = int(data.get("totalResults", 0))
            items: list[dict[str, Any]] = data.get("vulnerabilities", [])

            for item in items:
                try:
                    cves.append(_parse_cve_item(item))
                except (KeyError, ValueError) as exc:
                    logger.warning("Skipping malformed CVE item: %s", exc)

            start_index += len(items)
            logger.info(
                "NVD fetch: %d/%d CVEs loaded (page start=%d)",
                start_index,
                total,
                start_index - len(items),
            )

            if start_index >= total or not items:
                break

            await asyncio.sleep(self._settings.rate_limit_delay)

        return cves
