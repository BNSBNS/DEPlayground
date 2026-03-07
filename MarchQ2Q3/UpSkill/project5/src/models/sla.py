from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class SLARecord(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    contract_id: uuid.UUID
    period_start: datetime
    period_end: datetime
    expected_updates: int
    actual_updates: int
    missed_updates: int
    max_observed_latency: float  # seconds
    availability_pct: float
    compliant: bool
