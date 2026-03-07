from __future__ import annotations

import enum
import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ContractStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    deprecated = "deprecated"
    archived = "archived"


class Contract(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str
    dataset: str
    owner_team: str
    owner_contact: str
    status: ContractStatus = ContractStatus.draft
    current_version_id: uuid.UUID | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
