"""API request/response schemas for the fraud scoring API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ScoringRequest(BaseModel):
    """Single transaction scoring request."""

    transaction_id: str
    user_id: str
    features: dict[str, float] = Field(
        ..., description="Feature name → value mapping (all 20 features)"
    )
    ip_address: str | None = None


class ScoringResponse(BaseModel):
    """Single transaction scoring response."""

    transaction_id: str
    fraud_score: float = Field(..., ge=0.0, le=1.0)
    is_fraud: bool
    explanation: list[FeatureContribution]
    alert_emitted: bool = False


class FeatureContribution(BaseModel):
    """A feature's contribution to the fraud score."""

    feature: str
    contribution: float


class BatchScoringRequest(BaseModel):
    """Batch scoring request."""

    transactions: list[ScoringRequest]


class BatchScoringResponse(BaseModel):
    """Batch scoring response."""

    results: list[ScoringResponse]
    total: int
    flagged: int


class ModelInfo(BaseModel):
    """Model metadata."""

    model_name: str
    model_type: str
    feature_count: int
    feature_names: list[str]


class StatsResponse(BaseModel):
    """API usage statistics."""

    total_scored: int
    total_flagged: int
    flagged_rate: float
    avg_score: float


# Fix forward reference — ScoringResponse references FeatureContribution
ScoringResponse.model_rebuild()
