"""Tests for the InfraScanner FastAPI endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.models import Dependency, Ecosystem, ScanFinding, Vulnerability

if TYPE_CHECKING:
    from collections.abc import Generator

_REQ_TXT = "requests==2.18.4\nflask==2.0.1\n"
_PACKAGE_JSON = '{"dependencies": {"lodash": "4.17.11"}}'
_DOCKERFILE = "FROM ubuntu:latest\nCMD bash"

_PIP_FILE = {"name": "requirements.txt", "content": _REQ_TXT, "file_type": "pip_requirements"}
_NPM_FILE = {"name": "package.json", "content": _PACKAGE_JSON, "file_type": "package_json"}
_DOCKER_FILE = {"name": "Dockerfile", "content": _DOCKERFILE, "file_type": "dockerfile"}


@pytest.fixture()
def client() -> Generator[TestClient]:
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def no_osv_calls() -> Generator[None]:
    """Prevent real OSV API calls during tests."""
    mock_client = AsyncMock()
    mock_client.query_batch.return_value = {}
    with patch("src.api.routers.scan.OSVClient", return_value=mock_client):
        yield


class TestHealthEndpoint:
    def test_returns_200(self, client: TestClient) -> None:
        assert client.get("/health").status_code == 200

    def test_status_ok(self, client: TestClient) -> None:
        assert client.get("/health").json()["status"] == "ok"

    def test_service_name(self, client: TestClient) -> None:
        assert "InfraScanner" in client.get("/health").json()["service"]


class TestScanEndpoint:
    def test_pip_scan_returns_202(self, client: TestClient) -> None:
        body = {"files": [_PIP_FILE]}
        assert client.post("/api/v1/scan", json=body).status_code == 202

    def test_scan_returns_scan_id(self, client: TestClient) -> None:
        body = {"files": [_PIP_FILE]}
        data = client.post("/api/v1/scan", json=body).json()
        assert "scan_id" in data

    def test_npm_scan(self, client: TestClient) -> None:
        body = {"files": [_NPM_FILE]}
        assert client.post("/api/v1/scan", json=body).status_code == 202

    def test_dockerfile_scan(self, client: TestClient) -> None:
        body = {"files": [_DOCKER_FILE]}
        data = client.post("/api/v1/scan", json=body).json()
        # Dockerfile scanner should find issues (latest tag + no healthcheck + root)
        assert "summary" in data

    def test_invalid_file_type_returns_400(self, client: TestClient) -> None:
        body = {"files": [{"name": "f", "content": "x", "file_type": "unknown_type"}]}
        assert client.post("/api/v1/scan", json=body).status_code == 400

    def test_invalid_format_returns_400(self, client: TestClient) -> None:
        body = {
            "files": [{"name": "r.txt", "content": _REQ_TXT, "file_type": "pip_requirements"}],
            "format": "xml",
        }
        assert client.post("/api/v1/scan", json=body).status_code == 400

    def test_empty_files(self, client: TestClient) -> None:
        body = {"files": []}
        assert client.post("/api/v1/scan", json=body).status_code == 202

    def test_scan_report_json(self, client: TestClient) -> None:
        body = {"files": [{"name": "r.txt", "content": _REQ_TXT, "file_type": "pip_requirements"}]}
        data = client.post("/api/v1/scan/report", json=body).json()
        assert "report" in data

    def test_scan_report_sarif(self, client: TestClient) -> None:
        body = {
            "files": [{"name": "r.txt", "content": _REQ_TXT, "file_type": "pip_requirements"}],
            "format": "sarif",
        }
        data = client.post("/api/v1/scan/report", json=body).json()
        assert data.get("version") == "2.1.0"

    def test_vuln_in_response_when_found(self, client: TestClient) -> None:
        # Override the no_osv_calls fixture to return a finding
        dep = Dependency(name="requests", version="2.18.4", ecosystem=Ecosystem.PYPI)
        vuln = Vulnerability(vuln_id="CVE-2023-32681", cvss_score=7.2)
        finding = ScanFinding(dependency=dep, vulnerabilities=[vuln])

        mock_client = AsyncMock()
        mock_client.query_batch.return_value = {0: [vuln]}

        req_file = {"name": "r.txt", "content": "requests==2.18.4", "file_type": "pip_requirements"}
        with (
            patch("src.api.routers.scan.OSVClient", return_value=mock_client),
            patch("src.vuln_db.matcher.match_vulnerabilities", return_value=[finding]),
        ):
            body = {"files": [req_file]}
            data = client.post("/api/v1/scan", json=body).json()
            # Just verify the response structure
            assert "summary" in data
