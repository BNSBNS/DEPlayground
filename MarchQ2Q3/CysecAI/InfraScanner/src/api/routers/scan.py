"""Scan router — accept dependency file content and run analysis."""

from __future__ import annotations

import tempfile
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.models import Dependency, ScanResult
from src.parsers.go_parser import parse_go_mod
from src.parsers.npm_parser import parse_package_json
from src.parsers.pip_parser import parse_pyproject, parse_requirements
from src.reporting.ci_output import to_json, to_sarif
from src.scanners.docker_scanner import scan_dockerfile
from src.scanners.typosquat_detector import detect_typosquats
from src.vuln_db.matcher import match_vulnerabilities
from src.vuln_db.osv_client import OSVClient

router = APIRouter(prefix="/api/v1", tags=["scan"])

_VALID_TYPES = {"pip_requirements", "pyproject", "package_json", "go_mod", "dockerfile"}
_VALID_FORMATS = {"json", "sarif"}


class FileInput(BaseModel):
    name: str
    content: str
    file_type: str  # One of _VALID_TYPES


class ScanRequest(BaseModel):
    files: list[FileInput]
    format: str = "json"


@router.post("/scan", status_code=202)
async def scan(body: ScanRequest) -> dict[str, Any]:
    """Scan dependency files and return findings."""
    if body.format not in _VALID_FORMATS:
        raise HTTPException(status_code=400, detail=f"Invalid format: {body.format!r}")

    all_deps: list[Dependency] = []
    docker_content: str = ""

    for f in body.files:
        ftype = f.file_type.lower()
        if ftype not in _VALID_TYPES:
            raise HTTPException(status_code=400, detail=f"Unknown file_type: {ftype!r}")
        if ftype == "pip_requirements":
            all_deps.extend(parse_requirements(f.content, source_file=f.name))
        elif ftype == "pyproject":
            all_deps.extend(parse_pyproject(f.content, source_file=f.name))
        elif ftype == "package_json":
            all_deps.extend(parse_package_json(f.content, source_file=f.name))
        elif ftype == "go_mod":
            all_deps.extend(parse_go_mod(f.content, source_file=f.name))
        elif ftype == "dockerfile":
            docker_content = f.content

    with tempfile.TemporaryDirectory() as tmp:
        result = ScanResult(target_path=tmp)
        result.dependencies = all_deps

        osv = OSVClient()
        result.findings = await match_vulnerabilities(all_deps, osv)

        result.typosquat_findings = detect_typosquats(all_deps)

        if docker_content:
            result.docker_findings = scan_dockerfile(docker_content)

    return {"scan_id": result.scan_id, "summary": result.to_dict()}


@router.post("/scan/report")
async def scan_report(body: ScanRequest) -> dict[str, Any]:
    """Scan and return in requested format (json or sarif)."""
    if body.format not in _VALID_FORMATS:
        raise HTTPException(status_code=400, detail=f"Invalid format: {body.format!r}")

    all_deps: list[Dependency] = []
    docker_content = ""

    for f in body.files:
        ftype = f.file_type.lower()
        if ftype == "pip_requirements":
            all_deps.extend(parse_requirements(f.content, f.name))
        elif ftype == "pyproject":
            all_deps.extend(parse_pyproject(f.content, f.name))
        elif ftype == "package_json":
            all_deps.extend(parse_package_json(f.content, f.name))
        elif ftype == "go_mod":
            all_deps.extend(parse_go_mod(f.content, f.name))
        elif ftype == "dockerfile":
            docker_content = f.content

    with tempfile.TemporaryDirectory() as tmp:
        result = ScanResult(target_path=tmp)
        result.dependencies = all_deps
        result.findings = await match_vulnerabilities(all_deps, OSVClient())
        result.typosquat_findings = detect_typosquats(all_deps)
        if docker_content:
            result.docker_findings = scan_dockerfile(docker_content)

    if body.format == "sarif":
        return to_sarif(result)
    return {"report": to_json(result)}
