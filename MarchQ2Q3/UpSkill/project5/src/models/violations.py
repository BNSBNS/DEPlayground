from __future__ import annotations

import enum
import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ViolationType(str, enum.Enum):
    schema_mismatch = "schema_mismatch"
    quality_failure = "quality_failure"
    sla_breach = "sla_breach"


class ViolationSeverity(str, enum.Enum):
    warning = "warning"
    error = "error"
    critical = "critical"


class Violation(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    contract_id: uuid.UUID
    version_id: uuid.UUID
    violation_type: ViolationType
    severity: ViolationSeverity
    dataset: str
    field_name: str | None = None
    expected: str | None = None
    actual: str | None = None
    message: str
    detected_at: datetime = Field(default_factory=datetime.utcnow)
