"""Integration tests — require the full Docker stack to be running.

Setup:
    make docker-up   # start Postgres + app
    make seed        # populate simulated tables
    pytest tests/integration -m integration -v

These tests hit the live API (localhost:8010) and verify end-to-end behaviour.
They are skipped automatically if the API isn't reachable.
"""

from __future__ import annotations

import pytest
import httpx

BASE_URL = "http://localhost:8010"
pytestmark = pytest.mark.integration


@pytest.fixture(scope="session", autouse=True)
def require_api() -> None:
    """Skip the entire module if the API isn't running."""
    try:
        r = httpx.get(f"{BASE_URL}/health", timeout=3.0)
        if r.status_code != 200:
            pytest.skip("API returned non-200 — run `make docker-up`")
    except httpx.ConnectError:
        pytest.skip("API unreachable — run `make docker-up`")


# ── Health ─────────────────────────────────────────────────────────────────────

def test_health_returns_status() -> None:
    r = httpx.get(f"{BASE_URL}/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in ("healthy", "degraded")
    assert "database" in body["checks"]


def test_health_database_connected() -> None:
    r = httpx.get(f"{BASE_URL}/health")
    body = r.json()
    assert body["checks"]["database"] == "ok", (
        "Database not connected — is Postgres running? (make docker-up)"
    )


# ── Metrics ────────────────────────────────────────────────────────────────────

def test_metrics_list_returns_list() -> None:
    r = httpx.get(f"{BASE_URL}/api/v1/metrics")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_metrics_check_freshness_on_sim_events() -> None:
    """Run a live freshness check against sim_events (seeded by `make seed`)."""
    r = httpx.post(
        f"{BASE_URL}/api/v1/metrics/check",
        json={
            "table_name": "sim_events",
            "database": "default",
            "schema_name": "public",
            "metric_type": "freshness",
            "timestamp_column": "updated_at",
        },
        timeout=10.0,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["metric_type"] == "freshness"
    assert body["status"] in ("healthy", "warning", "critical", "unknown")
    assert isinstance(body["value"], float)


# ── Alerts ─────────────────────────────────────────────────────────────────────

def test_alerts_list_returns_list() -> None:
    r = httpx.get(f"{BASE_URL}/api/v1/alerts")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# ── Webhooks ───────────────────────────────────────────────────────────────────

def test_webhook_airflow_is_processed() -> None:
    r = httpx.post(
        f"{BASE_URL}/api/v1/webhooks/airflow",
        json={
            "dag_id": "test_dag",
            "task_id": "load_sim_events",
            "execution_date": "2024-01-01T00:00:00",
        },
        timeout=15.0,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "processed"
    assert "sim_events" in body.get("checked_tables", [])


def test_webhook_openlineage_complete_adds_edges() -> None:
    r = httpx.post(
        f"{BASE_URL}/api/v1/webhooks/openlineage",
        json={
            "event_type": "COMPLETE",
            "run_id": "test-run-001",
            "job_name": "test_transform",
            "inputs": [{"namespace": "postgres", "name": "raw_events"}],
            "outputs": [{"namespace": "postgres", "name": "processed_events"}],
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "processed"
    assert body["edges_added"] >= 1
