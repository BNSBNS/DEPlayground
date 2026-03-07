from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ValueType(str, Enum):
    INT64 = "int64"
    FLOAT64 = "float64"
    STRING = "string"
    BOOL = "bool"
    TIMESTAMP = "timestamp"
    JSON = "json"


class FeatureStatus(str, Enum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    EXPERIMENTAL = "experimental"


class AggSpec(BaseModel):
    function: str
    window: str
    filter: str | None = None


class FeatureDefinition(BaseModel):
    name: str
    feature_set: str
    entity: str
    value_type: ValueType
    description: str = ""
    owner: str = ""
    tags: list[str] = Field(default_factory=list)
    batch_source: str | None = None
    stream_source: str | None = None
    aggregation: AggSpec | None = None
    transform: str | None = None
    freshness_sla_minutes: int = 60
    version: int = 1
    status: FeatureStatus = FeatureStatus.ACTIVE


class FeatureSet(BaseModel):
    name: str
    entity: str
    features: list[str] = Field(default_factory=list)
    batch_source: str | None = None
    stream_source: str | None = None
    schedule: str = "daily"


class FeatureValue(BaseModel):
    entity_key: str
    feature_name: str
    value: Any = None
    event_timestamp: datetime
    created_timestamp: datetime = Field(default_factory=datetime.utcnow)
