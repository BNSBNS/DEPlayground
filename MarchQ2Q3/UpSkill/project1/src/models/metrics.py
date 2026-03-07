"""Data quality metric models."""

import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class MetricType(StrEnum):
    FRESHNESS = "freshness"
    VOLUME = "volume"
    DISTRIBUTION = "distribution"
    SCHEMA = "schema"
    CUSTOM = "custom"


class MetricStatus(StrEnum):
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class DataQualityMetric(BaseModel):
    """A single data quality measurement for a table."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    table_name: str
    database: str
    schema_name: str = Field(default="public")
    metric_type: MetricType
    value: float
    expected_value: float | None = None
    threshold_warning: float | None = None
    threshold_critical: float | None = None
    status: MetricStatus = MetricStatus.UNKNOWN
    metadata: dict[str, object] = Field(default_factory=dict)
    measured_at: datetime = Field(default_factory=datetime.utcnow)

    def derive_status(self) -> "DataQualityMetric":
        """Derive status from value vs thresholds. Returns self for chaining."""
        if self.threshold_critical is not None and self.value >= self.threshold_critical:
            self.status = MetricStatus.CRITICAL
        elif self.threshold_warning is not None and self.value >= self.threshold_warning:
            self.status = MetricStatus.WARNING
        elif self.threshold_warning is not None:
            self.status = MetricStatus.HEALTHY
        else:
            self.status = MetricStatus.UNKNOWN
        return self
