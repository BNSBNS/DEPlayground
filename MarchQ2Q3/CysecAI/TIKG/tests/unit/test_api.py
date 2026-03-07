"""Tests for TIKG FastAPI application."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.main import app


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


class TestHealth:
    def test_health_ok(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data


class TestNLQuery:
    def test_translate_cve_id(self, client: TestClient) -> None:
        resp = client.post("/api/v1/query", json={"question": "Show me CVE-2024-12345"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["intent"] == "cve_by_id"
        assert data["parameters"]["cve_id"] == "CVE-2024-12345"
        assert "MATCH" in data["cypher"]

    def test_translate_top_cves(self, client: TestClient) -> None:
        resp = client.post("/api/v1/query", json={"question": "Top 5 critical CVEs by score"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["intent"] == "top_cves"

    def test_translate_kev(self, client: TestClient) -> None:
        resp = client.post("/api/v1/query", json={"question": "Which CVEs are in the KEV catalog?"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["intent"] == "kev_status"

    def test_empty_question_returns_422(self, client: TestClient) -> None:
        resp = client.post("/api/v1/query", json={"question": "  "})
        assert resp.status_code == 422

    def test_unknown_question(self, client: TestClient) -> None:
        resp = client.post("/api/v1/query", json={"question": "What is the weather today?"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["intent"] == "unknown"
        assert data["confidence"] == 0.0

    def test_confidence_in_response(self, client: TestClient) -> None:
        resp = client.post("/api/v1/query", json={"question": "CVE-2024-12345"})
        assert resp.status_code == 200
        assert "confidence" in resp.json()

    def test_parameters_in_response(self, client: TestClient) -> None:
        resp = client.post("/api/v1/query", json={"question": "Show CVE-2021-44228"})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["parameters"], dict)


class TestIntents:
    def test_list_intents(self, client: TestClient) -> None:
        resp = client.get("/api/v1/intents")
        assert resp.status_code == 200
        data = resp.json()
        assert "intents" in data
        assert "cve_by_id" in data["intents"]
        assert "kev_status" in data["intents"]
        assert "unknown" in data["intents"]
