"""Core scanner models — Finding, Endpoint, ScanResult, enums."""

from __future__ import annotations

import datetime
import uuid
from enum import StrEnum

from pydantic import BaseModel, Field


class Severity(StrEnum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class OWASPCategory(StrEnum):
    API1_BOLA = "API1:2023 Broken Object Level Authorization"
    API2_AUTH = "API2:2023 Broken Authentication"
    API3_PROPERTY_AUTH = "API3:2023 Broken Object Property Level Authorization"
    API4_CONSUMPTION = "API4:2023 Unrestricted Resource Consumption"
    API5_FUNCTION_AUTH = "API5:2023 Broken Function Level Authorization"
    API6_BUSINESS_FLOW = "API6:2023 Unrestricted Access to Sensitive Business Flows"
    API7_SSRF = "API7:2023 Server-Side Request Forgery"
    API8_MISCONFIG = "API8:2023 Security Misconfiguration"
    API9_INVENTORY = "API9:2023 Improper Inventory Management"
    API10_CONSUMPTION = "API10:2023 Unsafe Consumption of APIs"


class Finding(BaseModel):
    finding_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    owasp_category: OWASPCategory
    title: str
    severity: Severity
    endpoint: str
    method: str = "GET"
    evidence: str
    remediation: str
    timestamp: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.UTC)
    )


class Endpoint(BaseModel):
    path: str
    method: str
    parameters: list[str] = Field(default_factory=list)
    requires_auth: bool = False
    description: str = ""


class ScanResult(BaseModel):
    scan_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    target_url: str
    findings: list[Finding] = Field(default_factory=list)
    endpoints_scanned: int = 0
    started_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.UTC)
    )
    completed_at: datetime.datetime | None = None

    def add_finding(self, finding: Finding) -> None:
        self.findings.append(finding)

    @property
    def finding_count(self) -> int:
        return len(self.findings)

    @property
    def critical_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.CRITICAL)

    @property
    def high_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.HIGH)
