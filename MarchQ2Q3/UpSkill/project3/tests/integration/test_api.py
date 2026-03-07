"""Integration tests — require the Docker stack running on port 8030.

Setup:
    make docker-up && make seed
    pytest tests/integration -m integration -v
"""

from __future__ import annotations

import pytest
import httpx

BASE_URL = "http://localhost:8030"
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


def test_events_list() -> None:
    r = httpx.get(f"{BASE_URL}/api/v1/events", timeout=5.0)
    assert r.status_code in (200, 404)  # 404 if no events yet


def test_approvals_list() -> None:
    r = httpx.get(f"{BASE_URL}/api/v1/approvals", timeout=5.0)
    assert r.status_code in (200, 404)


def test_pipeline_event_submission() -> None:
    """Submit a synthetic Airflow failure event — verifies the agent pipeline starts."""
    r = httpx.post(
        f"{BASE_URL}/api/v1/events",
        json={
            "source": "airflow",
            "event_type": "task_failure",
            "dag_id": "integration_test_dag",
            "task_id": "load_orders",
            "error_message": "Connection timeout",
            "execution_date": "2024-01-15T00:00:00Z",
        },
        timeout=10.0,
    )
    assert r.status_code in (200, 201, 202), f"Unexpected status: {r.status_code} {r.text}"
