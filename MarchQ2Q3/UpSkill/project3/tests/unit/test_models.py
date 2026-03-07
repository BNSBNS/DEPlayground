from uuid import UUID

from src.models.diagnosis import Diagnosis, DiagnosisCategory
from src.models.events import (
    ErrorType,
    EventSeverity,
    EventSource,
    PipelineFailureEvent,
)
from src.models.fixes import FixProposal, FixType, GeneratedFix, RiskLevel


class TestPipelineFailureEvent:
    def test_create_event(self) -> None:
        event = PipelineFailureEvent(
            source=EventSource.DBT,
            pipeline_name="test_pipeline",
            task_name="test_task",
            error_message="test error",
        )
        assert isinstance(event.event_id, UUID)
        assert event.source == EventSource.DBT
        assert event.severity == EventSeverity.MEDIUM
        assert event.error_type == ErrorType.UNKNOWN

    def test_event_with_all_fields(self) -> None:
        event = PipelineFailureEvent(
            source=EventSource.AIRFLOW,
            severity=EventSeverity.CRITICAL,
            pipeline_name="orders",
            task_name="load",
            error_message="column not found",
            error_type=ErrorType.SCHEMA_MISMATCH,
            affected_table="orders",
            affected_column="discount",
            schema_name="public",
            dag_id="dag_orders",
            run_id="run_123",
        )
        assert event.affected_table == "orders"
        assert event.dag_id == "dag_orders"


class TestDiagnosis:
    def test_create_diagnosis(self) -> None:
        d = Diagnosis(
            category=DiagnosisCategory.SCHEMA_DRIFT,
            confidence=0.9,
            explanation="Schema drift detected",
        )
        assert d.category == DiagnosisCategory.SCHEMA_DRIFT
        assert d.confidence == 0.9
        assert d.evidence == []

    def test_confidence_bounds(self) -> None:
        d = Diagnosis(
            category=DiagnosisCategory.UNKNOWN,
            confidence=0.0,
            explanation="Low confidence",
        )
        assert d.confidence == 0.0


class TestGeneratedFix:
    def test_create_fix(self) -> None:
        fix = GeneratedFix(
            fix_type=FixType.SQL_ALTER,
            content="ALTER TABLE t ADD COLUMN c TEXT;",
            description="Add column c",
        )
        assert fix.fix_type == FixType.SQL_ALTER
        assert fix.risk_level == RiskLevel.MEDIUM


class TestFixProposal:
    def test_empty_proposal(self) -> None:
        p = FixProposal()
        assert isinstance(p.proposal_id, UUID)
        assert p.fixes == []
        assert not p.requires_approval

    def test_proposal_with_fixes(self, sample_fix: GeneratedFix) -> None:
        p = FixProposal(fixes=[sample_fix])
        assert len(p.fixes) == 1
