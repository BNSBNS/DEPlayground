from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class FeatureStats(BaseModel):
    feature_name: str
    window_start: datetime
    window_end: datetime
    count: int = 0
    null_count: int = 0
    null_pct: float = 0.0
    mean: float | None = None
    stddev: float | None = None
    min: float | None = None
    max: float | None = None
    p25: float | None = None
    p50: float | None = None
    p75: float | None = None
    p95: float | None = None
    unique_count: int | None = None
    value_distribution: dict[str, int] = Field(default_factory=dict)
