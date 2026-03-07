"""CycloneDX 1.4 SBOM generator (JSON format)."""

from __future__ import annotations

import datetime
import uuid
from typing import Any

from src.models import Dependency, Ecosystem, SBOMComponent

_PURL_ECOSYSTEMS: dict[Ecosystem, str] = {
    Ecosystem.PYPI: "pypi",
    Ecosystem.NPM: "npm",
    Ecosystem.GO: "golang",
    Ecosystem.DOCKER: "docker",
}


def _make_purl(dep: Dependency) -> str:
    """Generate a Package URL (purl) for a dependency."""
    eco = _PURL_ECOSYSTEMS.get(dep.ecosystem, "generic")
    version_part = f"@{dep.version}" if dep.version else ""
    return f"pkg:{eco}/{dep.name}{version_part}"


def deps_to_components(deps: list[Dependency]) -> list[SBOMComponent]:
    """Convert dependencies to CycloneDX SBOM components."""
    return [
        SBOMComponent(
            name=dep.name,
            version=dep.version or "",
            purl=_make_purl(dep),
        )
        for dep in deps
    ]


def generate_sbom(
    components: list[SBOMComponent],
    metadata: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Generate a CycloneDX 1.4 SBOM as a Python dict (JSON-serialisable)."""
    meta = metadata or {}
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.4",
        "serialNumber": f"urn:uuid:{uuid.uuid4()}",
        "version": 1,
        "metadata": {
            "timestamp": datetime.datetime.now(tz=datetime.UTC).isoformat(),
            "tools": [
                {
                    "vendor": "InfraScanner",
                    "name": "infrascanner",
                    "version": "0.1.0",
                }
            ],
            "component": {
                "type": "application",
                "name": meta.get("name", "unknown"),
                "version": meta.get("version", ""),
            },
        },
        "components": [
            {
                "type": comp.type,
                "bom-ref": comp.bom_ref,
                "name": comp.name,
                "version": comp.version,
                "purl": comp.purl,
                "licenses": [{"license": {"id": lic}} for lic in comp.licenses],
                "hashes": [
                    {"alg": alg.upper(), "content": val} for alg, val in comp.hashes.items()
                ],
            }
            for comp in components
        ],
    }


def generate_sbom_from_deps(
    deps: list[Dependency],
    metadata: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Convenience: generate SBOM directly from dependency list."""
    components = deps_to_components(deps)
    return generate_sbom(components, metadata)
