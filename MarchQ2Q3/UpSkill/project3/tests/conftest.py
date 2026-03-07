from uuid import uuid4

import pytest

from src.models.diagnosis import Diagnosis, DiagnosisCategory
from src.models.events import (
    ErrorType,
    EventSeverity,
    EventSource,
    PipelineFailureEvent,
)
from src.models.fixes import FixProposal, FixType, GeneratedFix, RiskLevel


@pytest.fixture
def sample_event() -> PipelineFailureEvent:
    return PipelineFailureEvent(
        event_id=uuid4(),
        source=EventSource.DBT,
        severity=EventSeverity.HIGH,
        pipeline_name="daily_orders",
        task_name="stg_orders",
        error_message="column 'discount_amount' not found in source",
        error_type=ErrorType.SCHEMA_MISMATCH,
        affected_table="orders",
        affected_column="discount_amount",
        log_snippet="ERROR: column 'discount_amount' not found\nTraceback...",
    )


@pytest.fixture
def sample_diagnosis() -> Diagnosis:
    return Diagnosis(
        category=DiagnosisCategory.SCHEMA_DRIFT,
        confidence=0.85,
        explanation="Schema drift detected: missing column in source",
        evidence=["column 'discount_amount' not found"],
        affected_objects=["orders", "discount_amount"],
        suggested_approach="Add missing column via ALTER TABLE",
    )


@pytest.fixture
def sample_fix() -> GeneratedFix:
    return GeneratedFix(
        fix_type=FixType.SQL_ALTER,
        file_path="migrations/add_discount_amount_to_orders.sql",
        content=(
            "ALTER TABLE public.orders\n"
            "ADD COLUMN IF NOT EXISTS discount_amount TEXT DEFAULT '';"
        ),
        description="Add missing column 'discount_amount' to public.orders",
        risk_level=RiskLevel.MEDIUM,
    )


@pytest.fixture
def sample_proposal(sample_fix: GeneratedFix) -> FixProposal:
    return FixProposal(
        fixes=[sample_fix],
        pr_title="fix(orders): schema_drift - schema_mismatch",
        pr_body="Automated fix for schema drift",
    )


class FakeLLMProvider:
    """Fake LLM provider for testing."""

    def __init__(self, response: str = "SELECT 1;") -> None:
        self.response = response
        self.calls: list[str] = []

    async def generate(self, prompt: str) -> str:
        self.calls.append(prompt)
        return self.response

    async def generate_json(self, prompt: str) -> dict:
        self.calls.append(prompt)
        return {"fix": self.response}


@pytest.fixture
def fake_llm() -> FakeLLMProvider:
    return FakeLLMProvider()
