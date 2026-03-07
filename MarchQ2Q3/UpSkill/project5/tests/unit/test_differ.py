from __future__ import annotations

import uuid
from datetime import datetime

import pytest

from src.contracts.differ import diff_versions
from src.models.versions import ContractVersion


@pytest.fixture
def version_v1() -> ContractVersion:
    return ContractVersion(
        id=uuid.uuid4(),
        contract_id=uuid.uuid4(),
        version="1.0.0",
        schema_spec={
            "columns": {
                "id": {"type": "uuid", "nullable": False},
                "name": {"type": "text", "nullable": False},
                "status": {"type": "text", "nullable": False},
            }
        },
        quality_spec={"max_null_pct": 5.0},
        sla_spec={"max_latency_seconds": 300},
        consumers=["analytics-team", "billing-service"],
        changelog="Initial version",
        published_at=datetime(2025, 1, 1),
    )


@pytest.fixture
def version_v2(version_v1: ContractVersion) -> ContractVersion:
    return ContractVersion(
        id=uuid.uuid4(),
        contract_id=version_v1.contract_id,
        version="2.0.0",
        schema_spec={
            "columns": {
                "id": {"type": "uuid", "nullable": False},
                "name": {"type": "text", "nullable": False},
                # 'status' removed
                "category": {"type": "text", "nullable": True},  # added
            }
        },
        quality_spec={"max_null_pct": 2.0},
        sla_spec={"max_latency_seconds": 100},
        consumers=["analytics-team", "ml-pipeline"],
        changelog="Breaking changes: removed status, added category",
        published_at=datetime(2025, 2, 1),
    )


def test_diff_detects_removed_column(
    version_v1: ContractVersion, version_v2: ContractVersion
) -> None:
    diff = diff_versions(version_v1, version_v2)
    schema_changes = diff["schema_changes"]

    removed = [c for c in schema_changes if c["change"] == "column_removed"]
    assert len(removed) == 1
    assert removed[0]["column"] == "status"
    assert removed[0]["breaking"] is True


def test_diff_detects_added_column(
    version_v1: ContractVersion, version_v2: ContractVersion
) -> None:
    diff = diff_versions(version_v1, version_v2)
    schema_changes = diff["schema_changes"]

    added = [c for c in schema_changes if c["change"] == "column_added"]
    assert len(added) == 1
    assert added[0]["column"] == "category"
    assert added[0]["breaking"] is False


def test_diff_detects_quality_changes(
    version_v1: ContractVersion, version_v2: ContractVersion
) -> None:
    diff = diff_versions(version_v1, version_v2)
    quality_changes = diff["quality_changes"]

    assert len(quality_changes) == 1
    assert quality_changes[0]["field"] == "quality.max_null_pct"
    assert quality_changes[0]["old"] == "5.0"
    assert quality_changes[0]["new"] == "2.0"


def test_diff_detects_sla_changes(
    version_v1: ContractVersion, version_v2: ContractVersion
) -> None:
    diff = diff_versions(version_v1, version_v2)
    sla_changes = diff["sla_changes"]

    assert len(sla_changes) == 1
    assert sla_changes[0]["field"] == "sla.max_latency_seconds"


def test_diff_detects_consumer_changes(
    version_v1: ContractVersion, version_v2: ContractVersion
) -> None:
    diff = diff_versions(version_v1, version_v2)
    consumer_changes = diff["consumer_changes"]

    assert "billing-service" in consumer_changes["removed"]
    assert "ml-pipeline" in consumer_changes["added"]


def test_diff_version_labels(
    version_v1: ContractVersion, version_v2: ContractVersion
) -> None:
    diff = diff_versions(version_v1, version_v2)

    assert diff["from_version"] == "1.0.0"
    assert diff["to_version"] == "2.0.0"
    assert diff["changelog"] == "Breaking changes: removed status, added category"


def test_diff_no_changes() -> None:
    v = ContractVersion(
        id=uuid.uuid4(),
        contract_id=uuid.uuid4(),
        version="1.0.0",
        schema_spec={"columns": {"id": {"type": "uuid"}}},
        quality_spec={"max_null_pct": 5.0},
        sla_spec={},
        consumers=["team-a"],
    )
    diff = diff_versions(v, v)

    assert diff["schema_changes"] == []
    assert diff["quality_changes"] == []
    assert diff["sla_changes"] == []
    assert diff["consumer_changes"] == {"added": [], "removed": []}
