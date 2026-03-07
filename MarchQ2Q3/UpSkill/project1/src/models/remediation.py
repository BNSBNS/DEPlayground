"""Remediation log models."""

import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class RemediationResult(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class RemediationLog(BaseModel):
    """Record of a remediation action taken on an alert."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    alert_id: uuid.UUID
    action_type: str
    action_detail: dict[str, object] = Field(default_factory=dict)
    executed_by: str = "system"
    result: RemediationResult = RemediationResult.SKIPPED
    executed_at: datetime = Field(default_factory=datetime.utcnow)
