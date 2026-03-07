from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ErrorType(StrEnum):
    SCHEMA_MISMATCH = "schema_mismatch"
    NULL_VIOLATION = "null_violation"
    TYPE_MISMATCH = "type_mismatch"
    VOLUME_ANOMALY = "volume_anomaly"
    MISSING_SOURCE = "missing_source"
    PERMISSION_ERROR = "permission_error"
    TIMEOUT = "timeout"
    LOGIC_ERROR = "logic_error"
    UNKNOWN = "unknown"


class EventSource(StrEnum):
    AIRFLOW = "airflow"
    DBT = "dbt"
    GREAT_EXPECTATIONS = "great_expectations"
    CUSTOM = "custom"


class EventSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PipelineFailureEvent(BaseModel):
    """Represents a pipeline failure event received from an orchestrator."""

    event_id: UUID = Field(default_factory=uuid4)
    source: EventSource
    severity: EventSeverity = EventSeverity.MEDIUM
    pipeline_name: str
    task_name: str
    error_message: str
    error_type: ErrorType = ErrorType.UNKNOWN
    log_snippet: str = ""
    affected_table: str = ""
    affected_column: str = ""
    schema_name: str = "public"
    dag_id: str = ""
    run_id: str = ""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, str] = Field(default_factory=dict)
