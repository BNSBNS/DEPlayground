"""MITRE ATT&CK client — fetches techniques from the STIX/JSON bundle."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from src.models import AttackTechnique

logger = logging.getLogger(__name__)

# MITRE ATT&CK Enterprise STIX 2.1 bundle (GitHub raw)
_ENTERPRISE_URL = (
    "https://raw.githubusercontent.com/mitre/cti/master/enterprise-attack/enterprise-attack.json"
)


def _parse_technique(obj: dict[str, Any]) -> AttackTechnique | None:
    """Parse a STIX attack-pattern object into an AttackTechnique."""
    # Skip deprecated / revoked objects
    if obj.get("revoked") or obj.get("x_mitre_deprecated"):
        return None

    technique_id: str | None = None
    for ref in obj.get("external_references", []):
        if ref.get("source_name") == "mitre-attack":
            technique_id = str(ref.get("external_id", ""))
            break
    if not technique_id:
        return None

    name: str = str(obj.get("name", ""))
    description: str = str(obj.get("description", ""))
    platforms: list[str] = [str(p) for p in obj.get("x_mitre_platforms", [])]
    detection: str | None = obj.get("detection") or None

    # Tactic comes from the kill_chain_phases
    tactic = ""
    phases: list[dict[str, str]] = obj.get("kill_chain_phases", [])
    if phases:
        tactic = phases[0].get("phase_name", "")

    # Sub-techniques reference parent via x_mitre_is_subtechnique
    sub_techniques: list[str] = []  # populated separately if needed

    return AttackTechnique(
        technique_id=technique_id,
        name=name,
        description=description,
        tactic=tactic,
        sub_techniques=sub_techniques,
        detection=detection,
        platforms=platforms,
    )


class MITREClient:
    """Async client for the MITRE ATT&CK STIX bundle."""

    def __init__(self, url: str = _ENTERPRISE_URL) -> None:
        self._url = url
        self._client = httpx.AsyncClient(timeout=60.0)

    async def __aenter__(self) -> MITREClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self._client.aclose()

    async def fetch_techniques(self) -> list[AttackTechnique]:
        """Download the ATT&CK STIX bundle and return parsed techniques."""
        resp = await self._client.get(self._url)
        resp.raise_for_status()
        bundle: dict[str, Any] = resp.json()
        objects: list[dict[str, Any]] = bundle.get("objects", [])

        techniques: list[AttackTechnique] = []
        for obj in objects:
            if obj.get("type") != "attack-pattern":
                continue
            tech = _parse_technique(obj)
            if tech is not None:
                techniques.append(tech)

        logger.info("MITRE ATT&CK: loaded %d techniques", len(techniques))
        return techniques
