from __future__ import annotations

import uuid
from datetime import datetime

import pytest

from src.contracts.version_manager import VersionBump, compute_next_version
from src.models.versions import ContractVersion


@pytest.fixture
def base_version() -> ContractVersion:
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
        quality_spec={
            "rules": {
                "max_null_pct": 5.0,
                "min_volume": 10,
            }
        },
        sla_spec={
            "max_latency_seconds": 300,
            "min_availability_pct": 99.0,
        },
        consumers=["analytics-team"],
        changelog="Initial version",
        published_at=datetime(2025, 1, 1),
    )


def test_column_removal_is_major(base_version: ContractVersion) -> None:
    new_spec = {
        "schema": {
            "columns": {
                "id": {"type": "uuid", "nullable": False},
                "name": {"type": "text", "nullable": False},
                # 'status' column removed
            }
        },
        "quality": base_version.quality_spec,
        "sla": base_version.sla_spec,
    }
    next_ver, bump = compute_next_version(base_version, new_spec)
    assert bump == VersionBump.MAJOR
    assert next_ver == "2.0.0"


def test_type_change_is_major(base_version: ContractVersion) -> None:
    new_spec = {
        "schema": {
            "columns": {
                "id": {"type": "uuid", "nullable": False},
                "name": {"type": "text", "nullable": False},
                "status": {"type": "integer", "nullable": False},  # type changed
            }
        },
        "quality": base_version.quality_spec,
        "sla": base_version.sla_spec,
    }
    next_ver, bump = compute_next_version(base_version, new_spec)
    assert bump == VersionBump.MAJOR
    assert next_ver == "2.0.0"


def test_tightened_quality_is_major(base_version: ContractVersion) -> None:
    new_spec = {
        "schema": {"columns": base_version.schema_spec["columns"]},
        "quality": {
            "rules": {
                "max_null_pct": 1.0,  # tightened from 5.0
                "min_volume": 10,
            }
        },
        "sla": base_version.sla_spec,
    }
    next_ver, bump = compute_next_version(base_version, new_spec)
    assert bump == VersionBump.MAJOR


def test_tightened_sla_is_major(base_version: ContractVersion) -> None:
    new_spec = {
        "schema": {"columns": base_version.schema_spec["columns"]},
        "quality": base_version.quality_spec,
        "sla": {
            "max_latency_seconds": 100,  # tightened from 300
            "min_availability_pct": 99.0,
        },
    }
    next_ver, bump = compute_next_version(base_version, new_spec)
    assert bump == VersionBump.MAJOR


def test_new_column_is_minor(base_version: ContractVersion) -> None:
    new_spec = {
        "schema": {
            "columns": {
                "id": {"type": "uuid", "nullable": False},
                "name": {"type": "text", "nullable": False},
                "status": {"type": "text", "nullable": False},
                "category": {"type": "text", "nullable": True},  # new column
            }
        },
        "quality": base_version.quality_spec,
        "sla": base_version.sla_spec,
    }
    next_ver, bump = compute_next_version(base_version, new_spec)
    assert bump == VersionBump.MINOR
    assert next_ver == "1.1.0"


def test_loosened_quality_is_minor(base_version: ContractVersion) -> None:
    new_spec = {
        "schema": {"columns": base_version.schema_spec["columns"]},
        "quality": {
            "rules": {
                "max_null_pct": 10.0,  # loosened from 5.0
                "min_volume": 10,
            }
        },
        "sla": base_version.sla_spec,
    }
    next_ver, bump = compute_next_version(base_version, new_spec)
    assert bump == VersionBump.MINOR


def test_metadata_only_is_patch(base_version: ContractVersion) -> None:
    new_spec = {
        "schema": {"columns": base_version.schema_spec["columns"]},
        "quality": base_version.quality_spec,
        "sla": base_version.sla_spec,
    }
    next_ver, bump = compute_next_version(base_version, new_spec)
    assert bump == VersionBump.PATCH
    assert next_ver == "1.0.1"


def test_semver_increment_from_higher_version() -> None:
    version = ContractVersion(
        id=uuid.uuid4(),
        contract_id=uuid.uuid4(),
        version="3.2.5",
        schema_spec={"columns": {"id": {"type": "uuid"}}},
        quality_spec={},
        sla_spec={},
    )
    new_spec = {
        "schema": {"columns": {"id": {"type": "uuid"}}},
        "quality": {},
        "sla": {},
    }
    next_ver, bump = compute_next_version(version, new_spec)
    assert bump == VersionBump.PATCH
    assert next_ver == "3.2.6"
