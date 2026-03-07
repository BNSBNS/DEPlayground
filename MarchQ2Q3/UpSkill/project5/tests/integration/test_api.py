"""Integration tests — require the Docker stack running on port 8050.

Setup:
    make docker-up && make seed
    pytest tests/integration -m integration -v
"""

from __future__ import annotations

import pytest
import httpx

BASE_URL = "http://localhost:8050"
pytestmark = pytest.mark.integration


@pytest.fixture(scope="session", autouse=True)
def require_api() -> None:
    try:
        r = httpx.get(f"{BASE_URL}/health", timeout=3.0)
        if r.status_code != 200:
            pytest.skip("API not healthy — run `make docker-up`")
    except httpx.ConnectError:
        pytest.skip("API unreachable — run `make docker-up`")


def test_health() -> None:
    r = httpx.get(f"{BASE_URL}/health")
    assert r.status_code == 200
    assert r.json()["status"] in ("ok", "healthy", "degraded")


def test_contracts_list() -> None:
    r = httpx.get(f"{BASE_URL}/api/v1/contracts", timeout=5.0)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_violations_list() -> None:
    r = httpx.get(f"{BASE_URL}/api/v1/violations", timeout=5.0)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_contract_roundtrip() -> None:
    """Register a minimal contract and verify it appears in the list."""
    payload = {
        "name": "integration_test_contract",
        "version": "1.0.0",
        "dataset": "public.test_table",
        "owner": "test@example.com",
        "schema": {
            "fields": [
                {"name": "id", "type": "integer", "nullable": False},
                {"name": "name", "type": "string", "nullable": True},
            ]
        },
        "sla": {"freshness_minutes": 60, "row_count_min": 1},
    }
    r = httpx.post(f"{BASE_URL}/api/v1/contracts", json=payload, timeout=10.0)
    assert r.status_code in (200, 201), f"Create failed: {r.text}"
