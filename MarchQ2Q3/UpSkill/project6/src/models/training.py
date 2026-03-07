from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class TrainingDataset(BaseModel):
    id: str
    name: str
    entity_type: str
    features: list[str] = Field(default_factory=list)
    entity_df_ref: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    row_count: int = 0
