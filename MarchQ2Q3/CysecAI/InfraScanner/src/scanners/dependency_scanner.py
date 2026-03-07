"""Orchestrates dependency scanning: parse manifests, match vulns, detect typosquats."""

from __future__ import annotations

import pathlib

from src.models import Dependency, Ecosystem, ScanFinding, ScanResult
from src.parsers.go_parser import parse_go_file
from src.parsers.npm_parser import parse_npm_file
from src.parsers.pip_parser import parse_pip_file
from src.scanners.docker_scanner import scan_dockerfile
from src.scanners.typosquat_detector import detect_typosquats
from src.vuln_db.matcher import match_vulnerabilities
from src.vuln_db.osv_client import OSVClient

# File names we can parse
_PIP_FILES = {"requirements.txt", "requirements-dev.txt", "pyproject.toml"}
_NPM_FILES = {"package.json"}
_GO_FILES = {"go.mod"}
_DOCKER_FILES = {"dockerfile"}


def discover_manifests(root: pathlib.Path) -> list[pathlib.Path]:
    """Walk a directory and return all parseable manifest files."""
    found: list[pathlib.Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        name = path.name.lower()
        if name in _PIP_FILES | _NPM_FILES | _GO_FILES | _DOCKER_FILES:
            found.append(path)
    return found


def parse_manifest(path: pathlib.Path) -> list[Dependency]:
    """Parse a single manifest file into a list of dependencies."""
    name = path.name.lower()
    if name in _PIP_FILES:
        return parse_pip_file(path)
    if name in _NPM_FILES:
        return parse_npm_file(path)
    if name in _GO_FILES:
        return parse_go_file(path)
    return []


async def scan_project(
    target: pathlib.Path,
    osv_client: OSVClient | None = None,
    *,
    typosquat_max_distance: int = 2,
) -> ScanResult:
    """Full scan pipeline: discover → parse → vuln match → typosquat → docker."""
    result = ScanResult(target_path=str(target))

    # 1. Discover and parse dependency manifests
    all_deps: list[Dependency] = []
    manifests = discover_manifests(target) if target.is_dir() else [target]
    for manifest in manifests:
        all_deps.extend(parse_manifest(manifest))

    # Deduplicate by (name, version, ecosystem)
    seen: set[tuple[str, str | None, Ecosystem]] = set()
    unique_deps: list[Dependency] = []
    for dep in all_deps:
        key = (dep.name, dep.version, dep.ecosystem)
        if key not in seen:
            seen.add(key)
            unique_deps.append(dep)

    result.dependencies = unique_deps

    # 2. Vulnerability matching via OSV
    findings: list[ScanFinding] = await match_vulnerabilities(unique_deps, osv_client)
    result.findings = findings

    # 3. Typosquatting detection (no network needed)
    result.typosquat_findings = detect_typosquats(unique_deps, max_distance=typosquat_max_distance)

    # 4. Dockerfile checks
    docker_files = (
        [p for p in target.rglob("Dockerfile") if p.is_file()]
        if target.is_dir()
        else ([target] if target.name.lower() == "dockerfile" else [])
    )
    for df in docker_files:
        content = df.read_text(encoding="utf-8")
        result.docker_findings.extend(scan_dockerfile(content))

    return result
