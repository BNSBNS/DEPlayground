"""Core data models for DataSecurity."""

from __future__ import annotations

import datetime
import uuid
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class DataClassification(StrEnum):
    PII = "PII"  # Personally Identifiable Information
    PHI = "PHI"  # Protected Health Information
    PCI = "PCI"  # Payment Card Industry data
    PUBLIC = "PUBLIC"


class PIIType(StrEnum):
    EMAIL = "email"
    PHONE = "phone"
    NRIC = "nric"  # Singapore NRIC / national ID
    SSN = "ssn"  # US Social Security Number
    CREDIT_CARD = "credit_card"
    IP_ADDRESS = "ip_address"
    DATE_OF_BIRTH = "date_of_birth"
    NAME = "name"
    ADDRESS = "address"
    UNKNOWN = "unknown"


class MaskingStrategy(StrEnum):
    EMAIL = "email"
    PHONE = "phone"
    CREDIT_CARD = "credit_card"
    NAME = "name"
    FULL_REDACT = "full_redact"
    NONE = "none"


class ComplianceStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    NA = "N/A"


class SuspiciousQueryType(StrEnum):
    BULK_SELECT = "bulk_select"
    SCHEMA_DUMP = "schema_dump"
    PII_TABLE_WILDCARD = "pii_table_wildcard"
    OFF_HOURS = "off_hours"


class ColumnInfo(BaseModel):
    """Metadata for a single database column."""

    table_name: str
    column_name: str
    data_type: str
    nullable: bool = True
    classification: DataClassification = DataClassification.PUBLIC
    pii_types: list[PIIType] = Field(default_factory=list)
    masking_strategy: MaskingStrategy = MaskingStrategy.NONE
    sample_match: str | None = None


class TableInfo(BaseModel):
    """Metadata for a database table, including all columns."""

    table_name: str
    schema_name: str = "main"
    columns: list[ColumnInfo] = Field(default_factory=list)

    @property
    def pii_columns(self) -> list[ColumnInfo]:
        return [c for c in self.columns if c.classification != DataClassification.PUBLIC]

    @property
    def has_pii(self) -> bool:
        return len(self.pii_columns) > 0


class EncryptionStatus(BaseModel):
    """TDE and TLS status for a database connection."""

    database_name: str
    tde_enabled: bool = False
    tls_enabled: bool = False
    tde_details: str = ""
    tls_version: str = ""
    tls_cipher: str = ""


class AuditEvent(BaseModel):
    """A recorded database access event."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(tz=datetime.UTC)
    )
    db_user: str
    query_text: str
    tables_accessed: list[str] = Field(default_factory=list)
    row_count: int | None = None
    source_ip: str = ""
    is_suspicious: bool = False
    suspicious_reasons: list[SuspiciousQueryType] = Field(default_factory=list)


class MaskingResult(BaseModel):
    """Result of applying a masking strategy."""

    original_length: int
    masked_value: str
    strategy: MaskingStrategy


class ComplianceRequirement(BaseModel):
    """A single compliance requirement with its current status."""

    requirement_id: str
    framework: str  # PDPA, GDPR, PCI-DSS
    article: str
    description: str
    status: ComplianceStatus = ComplianceStatus.NA
    findings: list[str] = Field(default_factory=list)
    remediation: str = ""


class ComplianceReport(BaseModel):
    """Full compliance report for a scanned database."""

    report_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(tz=datetime.UTC)
    )
    database_name: str
    tables_scanned: list[str] = Field(default_factory=list)
    pii_columns_found: int = 0
    tde_enabled: bool = False
    tls_enabled: bool = False
    requirements: list[ComplianceRequirement] = Field(default_factory=list)

    @property
    def pass_count(self) -> int:
        return sum(1 for r in self.requirements if r.status == ComplianceStatus.PASS)

    @property
    def fail_count(self) -> int:
        return sum(1 for r in self.requirements if r.status == ComplianceStatus.FAIL)

    @property
    def risk_score(self) -> float:
        assessed = [r for r in self.requirements if r.status != ComplianceStatus.NA]
        if not assessed:
            return 0.0
        return round(
            sum(1 for r in assessed if r.status == ComplianceStatus.FAIL) / len(assessed), 2
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "timestamp": self.timestamp.isoformat(),
            "database_name": self.database_name,
            "summary": {
                "tables_scanned": len(self.tables_scanned),
                "pii_columns_found": self.pii_columns_found,
                "tde_enabled": self.tde_enabled,
                "tls_enabled": self.tls_enabled,
                "requirements_pass": self.pass_count,
                "requirements_fail": self.fail_count,
                "risk_score": self.risk_score,
            },
            "requirements": [
                {
                    "id": r.requirement_id,
                    "framework": r.framework,
                    "article": r.article,
                    "description": r.description,
                    "status": str(r.status),
                    "findings": r.findings,
                    "remediation": r.remediation,
                }
                for r in self.requirements
            ],
        }
