"""Tests for DataSecurity API endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from src.api.main import app

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> Generator[TestClient]:
    with TestClient(app) as c:
        yield c


class TestHealthEndpoint:
    def test_returns_200(self, client: TestClient) -> None:
        assert client.get("/health").status_code == 200

    def test_status_ok(self, client: TestClient) -> None:
        assert client.get("/health").json()["status"] == "ok"

    def test_service_name(self, client: TestClient) -> None:
        assert "DataSecurity" in client.get("/health").json()["service"]


class TestScanEndpoint:
    def test_empty_sqlite_returns_202(self, client: TestClient) -> None:
        body = {"db_url": "sqlite:///:memory:"}
        assert client.post("/api/v1/scan", json=body).status_code == 202

    def test_returns_report_id(self, client: TestClient) -> None:
        body = {"db_url": "sqlite:///:memory:"}
        data = client.post("/api/v1/scan", json=body).json()
        assert "report_id" in data

    def test_returns_report_summary(self, client: TestClient) -> None:
        body = {"db_url": "sqlite:///:memory:"}
        data = client.post("/api/v1/scan", json=body).json()
        assert "report" in data

    def test_html_format(self, client: TestClient) -> None:
        body = {"db_url": "sqlite:///:memory:", "format": "html"}
        data = client.post("/api/v1/scan", json=body).json()
        assert "html" in data
        assert "<html" in data["html"]

    def test_invalid_format_returns_400(self, client: TestClient) -> None:
        body = {"db_url": "sqlite:///:memory:", "format": "xml"}
        assert client.post("/api/v1/scan", json=body).status_code == 400

    def test_invalid_framework_returns_400(self, client: TestClient) -> None:
        body = {"db_url": "sqlite:///:memory:", "frameworks": ["HIPAA"]}
        assert client.post("/api/v1/scan", json=body).status_code == 400

    def test_postgres_url_rejected(self, client: TestClient) -> None:
        body = {"db_url": "postgresql://user:pass@localhost/db"}
        assert client.post("/api/v1/scan", json=body).status_code == 400

    def test_single_framework(self, client: TestClient) -> None:
        body = {"db_url": "sqlite:///:memory:", "frameworks": ["PDPA"]}
        data = client.post("/api/v1/scan", json=body).json()
        assert "report" in data


class TestScanPIIEndpoint:
    def test_empty_db_returns_zero_pii(self, client: TestClient) -> None:
        body = {"db_url": "sqlite:///:memory:"}
        data = client.post("/api/v1/scan/pii", json=body).json()
        assert data["pii_tables"] == 0
        assert data["pii_columns"] == []

    def test_returns_tables_scanned(self, client: TestClient) -> None:
        body = {"db_url": "sqlite:///:memory:"}
        data = client.post("/api/v1/scan/pii", json=body).json()
        assert "tables_scanned" in data
