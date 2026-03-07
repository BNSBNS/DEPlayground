"""Core data models for InfraScanner."""

from __future__ import annotations

import datetime
import uuid
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class Ecosystem(StrEnum):
    PYPI = "pypi"
    NPM = "npm"
    GO = "go"
    DOCKER = "docker"
    UNKNOWN = "unknown"


class Severity(StrEnum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    NONE = "NONE"
    UNKNOWN = "UNKNOWN"


class LicenseRisk(StrEnum):
    COPYLEFT = "copyleft"
    RESTRICTED = "restricted"
    ALLOWED = "allowed"
    UNKNOWN = "unknown"


class Dependency(BaseModel):
    """A single package dependency extracted from a manifest file."""

    name: str
    version: str | None = None
    constraint: str | None = None
    ecosystem: Ecosystem
    source_file: str = ""


class Vulnerability(BaseModel):
    """A known vulnerability matching a dependency."""

    vuln_id: str  # CVE-YYYY-NNNNN or GHSA-...
    description: str = ""
    cvss_score: float | None = None
    severity: Severity = Severity.UNKNOWN
    epss_score: float | None = None
    is_kev: bool = False
    affected_versions: list[str] = Field(default_factory=list)
    reference_urls: list[str] = Field(default_factory=list)


class ScanFinding(BaseModel):
    """A dependency paired with its matched vulnerabilities."""

    dependency: Dependency
    vulnerabilities: list[Vulnerability]
    risk_score: float = 0.0  # max(CVSS) × EPSS, used for prioritization


class DockerFinding(BaseModel):
    """A CIS Docker Benchmark check violation."""

    check_id: str
    description: str
    severity: Severity
    line_number: int | None = None
    recommendation: str = ""


class LicenseFinding(BaseModel):
    """A license risk finding for a dependency."""

    package: str
    license_id: str
    risk: LicenseRisk


class TyposquatFinding(BaseModel):
    """A package name suspiciously similar to a well-known package."""

    package: str
    similar_to: str
    distance: int
    ecosystem: Ecosystem


class SBOMComponent(BaseModel):
    """A CycloneDX SBOM component entry."""

    bom_ref: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: str = "library"
    name: str
    version: str = ""
    purl: str = ""
    licenses: list[str] = Field(default_factory=list)
    hashes: dict[str, str] = Field(default_factory=dict)


class ScanResult(BaseModel):
    """Complete result of scanning a project."""

    scan_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    target_path: str
    timestamp: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(tz=datetime.UTC)
    )
    dependencies: list[Dependency] = Field(default_factory=list)
    findings: list[ScanFinding] = Field(default_factory=list)
    docker_findings: list[DockerFinding] = Field(default_factory=list)
    license_findings: list[LicenseFinding] = Field(default_factory=list)
    typosquat_findings: list[TyposquatFinding] = Field(default_factory=list)

    @property
    def total_vulns(self) -> int:
        return sum(len(f.vulnerabilities) for f in self.findings)

    @property
    def critical_count(self) -> int:
        return sum(
            1 for f in self.findings for v in f.vulnerabilities if v.severity == Severity.CRITICAL
        )

    @property
    def high_count(self) -> int:
        return sum(
            1 for f in self.findings for v in f.vulnerabilities if v.severity == Severity.HIGH
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "scan_id": self.scan_id,
            "target_path": self.target_path,
            "timestamp": self.timestamp.isoformat(),
            "total_dependencies": len(self.dependencies),
            "total_vulnerabilities": self.total_vulns,
            "critical": self.critical_count,
            "high": self.high_count,
            "findings": [
                {
                    "package": f.dependency.name,
                    "version": f.dependency.version,
                    "ecosystem": str(f.dependency.ecosystem),
                    "risk_score": f.risk_score,
                    "vulnerabilities": [
                        {
                            "id": v.vuln_id,
                            "severity": str(v.severity),
                            "cvss": v.cvss_score,
                            "epss": v.epss_score,
                            "is_kev": v.is_kev,
                            "description": v.description[:200],
                        }
                        for v in f.vulnerabilities
                    ],
                }
                for f in self.findings
            ],
            "docker_findings": [
                {
                    "check_id": d.check_id,
                    "severity": str(d.severity),
                    "description": d.description,
                    "line": d.line_number,
                }
                for d in self.docker_findings
            ],
            "license_findings": [
                {"package": lf.package, "license": lf.license_id, "risk": str(lf.risk)}
                for lf in self.license_findings
            ],
            "typosquat_findings": [
                {
                    "package": t.package,
                    "similar_to": t.similar_to,
                    "distance": t.distance,
                }
                for t in self.typosquat_findings
            ],
        }
