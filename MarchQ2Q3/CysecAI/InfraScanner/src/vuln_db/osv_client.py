"""OSV.dev API client for package vulnerability lookups."""

from __future__ import annotations

from typing import Any

import httpx

from src.models import Dependency, Ecosystem, Severity, Vulnerability

_OSV_BATCH_URL = "https://api.osv.dev/v1/querybatch"

# Map OSV ecosystem names to our Ecosystem enum
_ECOSYSTEM_MAP: dict[Ecosystem, str] = {
    Ecosystem.PYPI: "PyPI",
    Ecosystem.NPM: "npm",
    Ecosystem.GO: "Go",
    Ecosystem.DOCKER: "PyPI",  # Fallback — docker images aren't in OSV
}

# Map CVSS severity labels to Severity enum
_SEV_MAP: dict[str, Severity] = {
    "CRITICAL": Severity.CRITICAL,
    "HIGH": Severity.HIGH,
    "MODERATE": Severity.MEDIUM,
    "MEDIUM": Severity.MEDIUM,
    "LOW": Severity.LOW,
    "NONE": Severity.NONE,
}


def _parse_severity(raw_severity: list[dict[str, Any]]) -> tuple[Severity, float | None]:
    """Extract the highest severity and CVSS score from OSV severity entries."""
    best: Severity = Severity.UNKNOWN
    best_score: float | None = None
    order = [
        Severity.CRITICAL,
        Severity.HIGH,
        Severity.MEDIUM,
        Severity.LOW,
        Severity.NONE,
        Severity.UNKNOWN,
    ]
    for entry in raw_severity:
        sev_label = str(entry.get("type", "")).upper()
        if sev_label in {"CVSS_V3", "CVSS_V2"}:
            # Score string like "CVSS:3.1/AV:N/.../S:8.8"
            score_str = str(entry.get("score", ""))
            # Try to parse CVSS vector base score from the last segment
            # OSV returns the base score as a float in some responses
            try:
                score_val = (
                    float(score_str.rsplit("/", maxsplit=1)[-1])
                    if "/" in score_str
                    else float(score_str)
                )
                if best_score is None or score_val > best_score:
                    best_score = score_val
                    if score_val >= 9.0:
                        candidate = Severity.CRITICAL
                    elif score_val >= 7.0:
                        candidate = Severity.HIGH
                    elif score_val >= 4.0:
                        candidate = Severity.MEDIUM
                    elif score_val > 0:
                        candidate = Severity.LOW
                    else:
                        candidate = Severity.NONE
                    if order.index(candidate) < order.index(best):
                        best = candidate
            except (ValueError, IndexError):
                pass
        # Also check database_specific severity labels
        db_specific = entry.get("database_specific", {})
        if isinstance(db_specific, dict):
            label = str(db_specific.get("severity", "")).upper()
            mapped = _SEV_MAP.get(label)
            if mapped and order.index(mapped) < order.index(best):
                best = mapped

    return best, best_score


def _parse_osv_vuln(raw: dict[str, Any]) -> Vulnerability:
    """Convert an OSV vulnerability dict to a Vulnerability model."""
    vuln_id = str(raw.get("id", "UNKNOWN"))

    # Prefer CVE alias if available
    aliases: list[str] = raw.get("aliases", [])
    cve_ids = [a for a in aliases if a.startswith("CVE-")]
    display_id = cve_ids[0] if cve_ids else vuln_id

    summary = str(raw.get("summary", raw.get("details", "")))[:500]

    severity, cvss_score = _parse_severity(raw.get("severity", []))

    refs: list[str] = [str(r.get("url", "")) for r in raw.get("references", []) if r.get("url")]

    # Extract affected version ranges as text
    affected_versions: list[str] = []
    for pkg in raw.get("affected", []):
        for rng in pkg.get("ranges", []):
            for evt in rng.get("events", []):
                if "introduced" in evt:
                    affected_versions.append(f">={evt['introduced']}")
                if "fixed" in evt:
                    affected_versions.append(f"<{evt['fixed']}")

    return Vulnerability(
        vuln_id=display_id,
        description=summary,
        cvss_score=cvss_score,
        severity=severity,
        affected_versions=affected_versions[:10],
        reference_urls=refs[:5],
    )


class OSVClient:
    """Async client for the OSV.dev batch query API."""

    def __init__(self, base_url: str = _OSV_BATCH_URL, timeout: float = 30.0) -> None:
        self._url = base_url
        self._timeout = timeout

    async def query_batch(self, dependencies: list[Dependency]) -> dict[int, list[Vulnerability]]:
        """Query OSV for all deps in a single batch call.

        Returns a dict mapping dep index → list of Vulnerability objects.
        """
        queries: list[dict[str, Any]] = []
        valid_indices: list[int] = []

        for idx, dep in enumerate(dependencies):
            if dep.ecosystem == Ecosystem.DOCKER:
                continue
            if not dep.version:
                continue
            osv_eco = _ECOSYSTEM_MAP.get(dep.ecosystem, "PyPI")
            queries.append(
                {
                    "package": {"name": dep.name, "ecosystem": osv_eco},
                    "version": dep.version,
                }
            )
            valid_indices.append(idx)

        if not queries:
            return {}

        payload: dict[str, list[dict[str, Any]]] = {"queries": queries}

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(self._url, json=payload)
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()

        results: dict[int, list[Vulnerability]] = {}
        for i, result in enumerate(data.get("results", [])):
            raw_vulns: list[dict[str, Any]] = result.get("vulns", [])
            if raw_vulns:
                dep_idx = valid_indices[i]
                results[dep_idx] = [_parse_osv_vuln(v) for v in raw_vulns]

        return results
