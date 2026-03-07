"""NVD 2.0 API client for CVSS score enrichment.

This is a standalone implementation for InfraScanner (the TIKG NVD client
is tightly coupled to TIKG's own models and settings).
"""

from __future__ import annotations

from typing import Any

import httpx

_NVD_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"


def _extract_cvss_score(data: dict[str, Any]) -> tuple[float | None, str]:
    """Extract CVSS v3 base score and severity from NVD cve.metrics."""
    metrics = data.get("metrics", {})
    for key in ("cvssMetricV31", "cvssMetricV30"):
        entries: list[dict[str, Any]] = metrics.get(key, [])
        if entries:
            d = entries[0].get("cvssData", {})
            score = d.get("baseScore")
            severity = str(d.get("baseSeverity", "UNKNOWN")).upper()
            if score is not None:
                return float(score), severity
    # Fall back to v2
    v2_entries: list[dict[str, Any]] = metrics.get("cvssMetricV2", [])
    if v2_entries:
        d = v2_entries[0].get("cvssData", {})
        score = d.get("baseScore")
        if score is not None:
            return float(score), str(v2_entries[0].get("baseSeverity", "UNKNOWN")).upper()
    return None, "UNKNOWN"


class NVDClient:
    """Async client for NVD CVE API — used for CVSS score enrichment."""

    def __init__(
        self,
        base_url: str = _NVD_URL,
        api_key: str = "",
        timeout: float = 30.0,
    ) -> None:
        self._base_url = base_url
        self._headers: dict[str, str] = {"Accept": "application/json"}
        if api_key:
            self._headers["apiKey"] = api_key
        self._timeout = timeout

    async def get_cvss(self, cve_id: str) -> tuple[float | None, str]:
        """Fetch CVSS score for a specific CVE ID.

        Returns (base_score, severity) or (None, "UNKNOWN") on error.
        """
        params: dict[str, str] = {"cveId": cve_id}
        async with httpx.AsyncClient(headers=self._headers, timeout=self._timeout) as client:
            try:
                resp = await client.get(self._base_url, params=params)
                resp.raise_for_status()
                data: dict[str, Any] = resp.json()
                vulns: list[dict[str, Any]] = data.get("vulnerabilities", [])
                if vulns:
                    return _extract_cvss_score(vulns[0].get("cve", {}))
            except (httpx.HTTPError, KeyError, ValueError):
                pass
        return None, "UNKNOWN"
