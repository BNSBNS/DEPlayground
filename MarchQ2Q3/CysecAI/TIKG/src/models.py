"""Core Pydantic models for TIKG — CVE, CWE, AttackTechnique, KEVEntry, Software."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 — Pydantic needs runtime access

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# CVE / NVD models
# ---------------------------------------------------------------------------


class CVSSScore(BaseModel):
    """CVSS score (v2 or v3)."""

    version: str
    base_score: float
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW, NONE
    vector_string: str = ""


class CPEMatch(BaseModel):
    """CPE match entry — identifies affected software."""

    cpe_name: str
    vulnerable: bool = True
    version_start_including: str | None = None
    version_end_excluding: str | None = None


class CVE(BaseModel):
    """CVE entry from NVD 2.0 API."""

    cve_id: str
    description: str
    published: datetime
    last_modified: datetime
    cvss_v3: CVSSScore | None = None
    cvss_v2: CVSSScore | None = None
    cwe_ids: list[str] = Field(default_factory=list)
    cpe_matches: list[CPEMatch] = Field(default_factory=list)
    reference_urls: list[str] = Field(default_factory=list)
    epss_score: float | None = None  # enriched later

    @property
    def severity(self) -> str:
        """Return highest available severity label."""
        if self.cvss_v3:
            return self.cvss_v3.severity
        if self.cvss_v2:
            return self.cvss_v2.severity
        return "UNKNOWN"

    @property
    def base_score(self) -> float | None:
        """Return highest available CVSS base score."""
        if self.cvss_v3:
            return self.cvss_v3.base_score
        if self.cvss_v2:
            return self.cvss_v2.base_score
        return None


# ---------------------------------------------------------------------------
# MITRE ATT&CK models
# ---------------------------------------------------------------------------


class AttackTechnique(BaseModel):
    """MITRE ATT&CK technique."""

    technique_id: str  # e.g. "T1059"
    name: str
    description: str
    tactic: str  # e.g. "execution"
    sub_techniques: list[str] = Field(default_factory=list)
    detection: str | None = None
    platforms: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# CISA KEV models
# ---------------------------------------------------------------------------


class KEVEntry(BaseModel):
    """CISA Known Exploited Vulnerability catalog entry."""

    cve_id: str
    vendor_project: str
    product: str
    vulnerability_name: str
    date_added: datetime
    short_description: str
    required_action: str
    due_date: datetime | None = None


# ---------------------------------------------------------------------------
# Graph node models
# ---------------------------------------------------------------------------


class Software(BaseModel):
    """Software node in the knowledge graph."""

    vendor: str
    product: str
    version: str | None = None

    @property
    def node_id(self) -> str:
        v = self.version or "*"
        return f"{self.vendor}:{self.product}:{v}"


class CWE(BaseModel):
    """Common Weakness Enumeration entry."""

    cwe_id: str  # e.g. "CWE-79"
    name: str = ""
    description: str = ""
