from enum import StrEnum

from pydantic import BaseModel, Field


class DiagnosisCategory(StrEnum):
    SCHEMA_DRIFT = "schema_drift"
    DATA_QUALITY = "data_quality"
    INFRASTRUCTURE = "infrastructure"
    LOGIC_ERROR = "logic_error"
    DEPENDENCY = "dependency"
    PERMISSION = "permission"
    UNKNOWN = "unknown"


class Diagnosis(BaseModel):
    """Root-cause diagnosis for a pipeline failure."""

    category: DiagnosisCategory
    confidence: float = Field(ge=0.0, le=1.0)
    explanation: str
    evidence: list[str] = Field(default_factory=list)
    affected_objects: list[str] = Field(default_factory=list)
    suggested_approach: str = ""
