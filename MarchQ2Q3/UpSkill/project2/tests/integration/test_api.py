"""Integration tests — require the Docker stack running on port 8020.

Setup:
    make docker-up && make seed
    pytest tests/integration -m integration -v
"""

from __future__ import annotations

import pytest
import httpx

BASE_URL = "http://localhost:8020"
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
    body = r.json()
    assert body["status"] in ("ok", "degraded")


def test_ready() -> None:
    r = httpx.get(f"{BASE_URL}/ready")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_query_endpoint_reachable() -> None:
    """Verify the query endpoint accepts requests (may return empty result without data)."""
    r = httpx.post(
        f"{BASE_URL}/api/v1/query",
        json={"question": "What tables are in the database?"},
        timeout=30.0,
    )
    # Accept 200 (has data) or 422 (schema mismatch) but not 500
    assert r.status_code != 500, f"Server error: {r.text}"
