from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models.contracts import Contract, ContractStatus
from src.models.versions import ContractVersion
from src.models.violations import Violation, ViolationSeverity, ViolationType


@pytest.fixture
def sample_contract() -> Contract:
    return Contract(
        id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        name="Orders Contract",
        dataset="orders",
        owner_team="platform-engineering",
        owner_contact="platform-eng@company.com",
        status=ContractStatus.active,
        current_version_id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
        created_at=datetime(2025, 1, 1),
        updated_at=datetime(2025, 1, 1),
    )


@pytest.fixture
def sample_version() -> ContractVersion:
    return ContractVersion(
        id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
        contract_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        version="1.0.0",
        schema_spec={
            "schema": "public",
            "table": "orders",
            "columns": {
                "id": {"type": "uuid", "nullable": False},
                "customer_id": {"type": "uuid", "nullable": False},
                "total_amount": {"type": "numeric", "nullable": False},
                "status": {"type": "text", "nullable": False},
                "created_at": {"type": "timestamptz", "nullable": False},
            },
        },
        quality_spec={
            "rules": {
                "freshness": {
                    "timestamp_column": "updated_at",
                    "max_staleness_seconds": 3600,
                },
                "volume": {"min_rows": 100, "window_hours": 24},
                "completeness": {
                    "max_null_pct": 1.0,
                    "columns": ["customer_id", "total_amount"],
                },
                "uniqueness": {"columns": ["id"]},
            }
        },
        sla_spec={
            "update_frequency_minutes": 15,
            "max_latency_seconds": 120,
            "min_availability_pct": 99.5,
            "window_hours": 24,
            "timestamp_column": "updated_at",
        },
        consumers=["analytics-team", "billing-service"],
        changelog="Initial version",
        published_at=datetime(2025, 1, 1),
    )


@pytest.fixture
def sample_violation() -> Violation:
    return Violation(
        contract_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        version_id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
        violation_type=ViolationType.schema_mismatch,
        severity=ViolationSeverity.error,
        dataset="orders",
        field_name="status",
        expected="text",
        actual="integer",
        message="Column 'status' type mismatch: expected text, got integer",
    )


@pytest.fixture
def sample_contract_yaml(tmp_path: Path) -> Path:
    content = """\
metadata:
  name: Test Contract
  dataset: test_table
  owner_team: test-team
  owner_contact: test@company.com
  status: draft

version: "1.0.0"

schema:
  schema: public
  table: test_table
  columns:
    id:
      type: uuid
      nullable: false
    name:
      type: text
      nullable: false
    created_at:
      type: timestamptz
      nullable: false

quality:
  rules:
    freshness:
      timestamp_column: created_at
      max_staleness_seconds: 3600
    volume:
      min_rows: 10
      window_hours: 24
      timestamp_column: created_at
    completeness:
      max_null_pct: 5.0
      columns:
        - name
    uniqueness:
      columns:
        - id

sla:
  update_frequency_minutes: 60
  max_latency_seconds: 300
  min_availability_pct: 99.0
  window_hours: 24
  timestamp_column: created_at

consumers:
  - analytics-team

changelog: "Initial test contract"
"""
    p = tmp_path / "test_contract.yml"
    p.write_text(content, encoding="utf-8")
    return p


@pytest.fixture
def mock_pool() -> AsyncMock:
    pool = AsyncMock()
    conn = AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
    return pool
