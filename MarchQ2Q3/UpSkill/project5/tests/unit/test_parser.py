from __future__ import annotations

from pathlib import Path

from src.contracts.parser import load_contract
from src.models.contracts import ContractStatus


def test_load_contract_from_yaml(sample_contract_yaml: Path) -> None:
    contract, version = load_contract(sample_contract_yaml)

    assert contract.name == "Test Contract"
    assert contract.dataset == "test_table"
    assert contract.owner_team == "test-team"
    assert contract.owner_contact == "test@company.com"
    assert contract.status == ContractStatus.draft
    assert contract.current_version_id == version.id


def test_load_contract_version_fields(sample_contract_yaml: Path) -> None:
    contract, version = load_contract(sample_contract_yaml)

    assert version.version == "1.0.0"
    assert version.contract_id == contract.id
    assert version.changelog == "Initial test contract"
    assert "analytics-team" in version.consumers


def test_load_contract_schema_spec(sample_contract_yaml: Path) -> None:
    _, version = load_contract(sample_contract_yaml)

    schema = version.schema_spec
    assert schema["table"] == "test_table"
    assert schema["schema"] == "public"
    assert "id" in schema["columns"]
    assert schema["columns"]["id"]["type"] == "uuid"
    assert schema["columns"]["id"]["nullable"] is False


def test_load_contract_quality_spec(sample_contract_yaml: Path) -> None:
    _, version = load_contract(sample_contract_yaml)

    quality = version.quality_spec
    rules = quality["rules"]
    assert rules["freshness"]["max_staleness_seconds"] == 3600
    assert rules["volume"]["min_rows"] == 10
    assert rules["completeness"]["max_null_pct"] == 5.0
    assert "id" in rules["uniqueness"]["columns"]


def test_load_contract_sla_spec(sample_contract_yaml: Path) -> None:
    _, version = load_contract(sample_contract_yaml)

    sla = version.sla_spec
    assert sla["update_frequency_minutes"] == 60
    assert sla["max_latency_seconds"] == 300
    assert sla["min_availability_pct"] == 99.0


def test_load_contract_creates_valid_uuids(sample_contract_yaml: Path) -> None:
    contract, version = load_contract(sample_contract_yaml)

    assert contract.id is not None
    assert version.id is not None
    assert contract.id != version.id
    assert version.contract_id == contract.id
