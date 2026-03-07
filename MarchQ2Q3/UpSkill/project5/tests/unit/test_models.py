from __future__ import annotations

import uuid
from datetime import datetime

import pytest

from src.models.contracts import Contract, ContractStatus
from src.models.sla import SLARecord
from src.models.versions import ContractVersion
from src.models.violations import Violation, ViolationSeverity, ViolationType


def test_contract_creation() -> None:
    contract = Contract(
        name="Test Contract",
        dataset="test_table",
        owner_team="test-team",
        owner_contact="test@example.com",
    )
    assert contract.name == "Test Contract"
    assert contract.dataset == "test_table"
    assert contract.status == ContractStatus.draft
    assert contract.id is not None
    assert contract.current_version_id is None


def test_contract_status_enum() -> None:
    assert ContractStatus.draft.value == "draft"
    assert ContractStatus.active.value == "active"
    assert ContractStatus.deprecated.value == "deprecated"
    assert ContractStatus.archived.value == "archived"


def test_contract_with_explicit_id() -> None:
    cid = uuid.uuid4()
    contract = Contract(
        id=cid,
        name="Explicit",
        dataset="ds",
        owner_team="t",
        owner_contact="c",
    )
    assert contract.id == cid


def test_contract_version_creation() -> None:
    cid = uuid.uuid4()
    version = ContractVersion(
        contract_id=cid,
        version="2.1.0",
        schema_spec={"table": "orders", "columns": {"id": {"type": "uuid"}}},
        quality_spec={"rules": {"freshness": {"max_staleness_seconds": 3600}}},
        sla_spec={"max_latency_seconds": 120},
        consumers=["team-a", "team-b"],
        changelog="Added quality rules",
    )
    assert version.contract_id == cid
    assert version.version == "2.1.0"
    assert "table" in version.schema_spec
    assert len(version.consumers) == 2


def test_contract_version_defaults() -> None:
    version = ContractVersion(
        contract_id=uuid.uuid4(),
        version="1.0.0",
    )
    assert version.schema_spec == {}
    assert version.quality_spec == {}
    assert version.sla_spec == {}
    assert version.consumers == []
    assert version.changelog == ""


def test_violation_creation() -> None:
    violation = Violation(
        contract_id=uuid.uuid4(),
        version_id=uuid.uuid4(),
        violation_type=ViolationType.schema_mismatch,
        severity=ViolationSeverity.error,
        dataset="orders",
        field_name="status",
        expected="text",
        actual="integer",
        message="Type mismatch",
    )
    assert violation.violation_type == ViolationType.schema_mismatch
    assert violation.severity == ViolationSeverity.error
    assert violation.field_name == "status"


def test_violation_type_enum() -> None:
    assert ViolationType.schema_mismatch.value == "schema_mismatch"
    assert ViolationType.quality_failure.value == "quality_failure"
    assert ViolationType.sla_breach.value == "sla_breach"


def test_violation_severity_enum() -> None:
    assert ViolationSeverity.warning.value == "warning"
    assert ViolationSeverity.error.value == "error"
    assert ViolationSeverity.critical.value == "critical"


def test_violation_optional_fields() -> None:
    violation = Violation(
        contract_id=uuid.uuid4(),
        version_id=uuid.uuid4(),
        violation_type=ViolationType.quality_failure,
        severity=ViolationSeverity.warning,
        dataset="orders",
        message="Volume too low",
    )
    assert violation.field_name is None
    assert violation.expected is None
    assert violation.actual is None


def test_sla_record_creation() -> None:
    now = datetime.utcnow()
    record = SLARecord(
        contract_id=uuid.uuid4(),
        period_start=datetime(2025, 1, 1),
        period_end=now,
        expected_updates=96,
        actual_updates=90,
        missed_updates=6,
        max_observed_latency=250.5,
        availability_pct=93.75,
        compliant=False,
    )
    assert record.expected_updates == 96
    assert record.actual_updates == 90
    assert record.missed_updates == 6
    assert record.max_observed_latency == 250.5
    assert record.availability_pct == 93.75
    assert record.compliant is False


def test_sla_record_compliant() -> None:
    record = SLARecord(
        contract_id=uuid.uuid4(),
        period_start=datetime(2025, 1, 1),
        period_end=datetime(2025, 1, 2),
        expected_updates=24,
        actual_updates=24,
        missed_updates=0,
        max_observed_latency=50.0,
        availability_pct=100.0,
        compliant=True,
    )
    assert record.compliant is True
    assert record.missed_updates == 0


def test_model_json_serialization() -> None:
    contract = Contract(
        name="Serialization Test",
        dataset="test_ds",
        owner_team="team",
        owner_contact="contact",
    )
    data = contract.model_dump(mode="json")
    assert isinstance(data["id"], str)
    assert data["name"] == "Serialization Test"
    assert data["status"] == "draft"
