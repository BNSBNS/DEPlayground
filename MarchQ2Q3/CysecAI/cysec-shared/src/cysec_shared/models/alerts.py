"""Common SecurityAlert schema (Foundations #8) for all CysecAI projects.

Every alert-producing project (FraudAndAnomaly, AIMMLSecurity, NetworkSecurity,
APISecurity, InfraScanner) emits alerts in this format. The SIEM
(SecurityDataPipeline) consumes and correlates them via Kafka topic `cysec.alerts`.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class AlertSeverity(StrEnum):
    """Alert severity levels aligned with common SIEM standards."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class SecurityAlert(BaseModel):
    """Common alert format across all CysecAI projects.

    Fields follow Foundations #8 spec. Every alert must include:
    - source_project: which project generated it
    - rule_id: which detection rule fired
    - severity: impact level
    - mitre_technique_id: MITRE ATT&CK mapping (when applicable)
    - evidence: project-specific detection evidence
    """

    alert_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source_project: str
    rule_id: str
    severity: Literal["critical", "high", "medium", "low", "info"]
    title: str
    description: str
    mitre_technique_id: str | None = None
    mitre_tactic: str | None = None
    cia_impact: list[str] = Field(default_factory=list)
    evidence: dict[str, Any] = Field(default_factory=dict)
    affected_asset: str
    source_ip: str | None = None
    dest_ip: str | None = None
    user: str | None = None
    recommendations: list[str] = Field(default_factory=list)
