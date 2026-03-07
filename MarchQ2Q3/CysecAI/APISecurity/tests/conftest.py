"""Shared pytest fixtures for APISecurity tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.vulnerable_app import main as vuln_main
from src.vulnerable_app.main import app


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def reset_db() -> None:
    """Reset vulnerable app DB to seed state before each test."""
    vuln_main.reset_db_for_tests()


@pytest.fixture()
def alice_token(client: TestClient) -> str:
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": "alice", "password": "alice_password"},
    )
    return str(resp.json()["access_token"])


@pytest.fixture()
def admin_token(client: TestClient) -> str:
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin_password"},
    )
    return str(resp.json()["access_token"])
