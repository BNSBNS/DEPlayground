from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ContractVersion(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    contract_id: uuid.UUID
    version: str  # semver e.g. "1.2.0"
    schema_spec: dict[str, Any] = Field(default_factory=dict)
    quality_spec: dict[str, Any] = Field(default_factory=dict)
    sla_spec: dict[str, Any] = Field(default_factory=dict)
    consumers: list[str] = Field(default_factory=list)
    changelog: str = ""
    published_at: datetime = Field(default_factory=datetime.utcnow)
