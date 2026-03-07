"""Tests for the NetworkSecurity FastAPI endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.api.routers import alerts as alerts_module

if TYPE_CHECKING:
    from collections.abc import Generator

_BASE_TS = 1735689600.0
_PACKET_DATA = [
    {
        "timestamp": _BASE_TS + i * 0.5,
        "src_ip": "192.168.1.99",
        "dst_ip": "10.0.0.1",
        "src_port": 54321,
        "dst_port": i + 1,
        "protocol": "TCP",
        "tcp_flags": "SYN",
        "payload_size": 0,
    }
    for i in range(25)
]

_CLOUD_DATA = [
    {
        "eventTime": "2026-01-01T00:00:00Z",
        "eventName": "AttachUserPolicy",
        "sourceIPAddress": "1.2.3.4",
        "userIdentity": {
            "type": "IAMUser",
            "userName": "attacker",
            "arn": "arn:aws:iam::123:user/attacker",
        },
        "eventSource": "iam.amazonaws.com",
        "awsRegion": "us-east-1",
    }
]


@pytest.fixture(autouse=True)
def reset_manager() -> None:
    """Reset the module-level alert manager before each test."""
    alerts_module._manager = None


@pytest.fixture()
def client() -> Generator[TestClient]:
    with TestClient(app) as c:
        yield c


class TestHealthEndpoint:
    def test_returns_200(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_status_ok(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert resp.json()["status"] == "ok"

    def test_service_name(self, client: TestClient) -> None:
        assert "service" in client.get("/health").json()


class TestAnalyzePackets:
    def test_returns_202(self, client: TestClient) -> None:
        resp = client.post("/api/v1/analyze/packets", json={"packets": _PACKET_DATA})
        assert resp.status_code == 202

    def test_packets_analyzed_count(self, client: TestClient) -> None:
        resp = client.post("/api/v1/analyze/packets", json={"packets": _PACKET_DATA})
        assert resp.json()["packets_analyzed"] == 25

    def test_port_scan_alerts_generated(self, client: TestClient) -> None:
        resp = client.post("/api/v1/analyze/packets", json={"packets": _PACKET_DATA})
        assert resp.json()["alerts_generated"] > 0

    def test_empty_packets(self, client: TestClient) -> None:
        resp = client.post("/api/v1/analyze/packets", json={"packets": []})
        assert resp.status_code == 202
        assert resp.json()["packets_analyzed"] == 0


class TestAnalyzeCloud:
    def test_cloudtrail_returns_202(self, client: TestClient) -> None:
        body = {"source": "cloudtrail", "events": _CLOUD_DATA}
        assert client.post("/api/v1/analyze/cloud", json=body).status_code == 202

    def test_cloudtrail_events_analyzed(self, client: TestClient) -> None:
        body = {"source": "cloudtrail", "events": _CLOUD_DATA}
        assert client.post("/api/v1/analyze/cloud", json=body).json()["events_analyzed"] == 1

    def test_cloudtrail_detects_iam_privesc(self, client: TestClient) -> None:
        body = {"source": "cloudtrail", "events": _CLOUD_DATA}
        assert client.post("/api/v1/analyze/cloud", json=body).json()["alerts_generated"] > 0

    def test_vpc_flow_source(self, client: TestClient) -> None:
        vpc_data = [
            {
                "start": 1735689600,
                "srcaddr": "1.2.3.4",
                "dstaddr": "10.0.0.1",
                "srcport": 12345,
                "dstport": 22,
                "action": "ACCEPT",
                "bytes": 0,
                "protocol": "6",
            }
        ]
        body = {"source": "vpc_flow", "events": vpc_data}
        assert client.post("/api/v1/analyze/cloud", json=body).status_code == 202

    def test_k8s_source(self, client: TestClient) -> None:
        k8s_data = [
            {
                "requestReceivedTimestamp": "2026-01-01T00:00:00Z",
                "verb": "get",
                "user": {"username": "admin"},
                "objectRef": {"resource": "pods"},
                "responseStatus": {"code": 200},
                "requestObject": {},
            }
        ]
        body = {"source": "k8s_audit", "events": k8s_data}
        assert client.post("/api/v1/analyze/cloud", json=body).status_code == 202

    def test_unknown_source_returns_400(self, client: TestClient) -> None:
        resp = client.post("/api/v1/analyze/cloud", json={"source": "unknown", "events": []})
        assert resp.status_code == 400


class TestListAlerts:
    def test_empty_initially(self, client: TestClient) -> None:
        resp = client.get("/api/v1/alerts")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_alerts_after_scan(self, client: TestClient) -> None:
        client.post("/api/v1/analyze/packets", json={"packets": _PACKET_DATA})
        alerts = client.get("/api/v1/alerts").json()
        assert len(alerts) > 0

    def test_filter_by_severity(self, client: TestClient) -> None:
        client.post("/api/v1/analyze/packets", json={"packets": _PACKET_DATA})
        alerts = client.get("/api/v1/alerts?severity=HIGH").json()
        assert all(a["severity"] == "HIGH" for a in alerts)

    def test_invalid_severity_returns_400(self, client: TestClient) -> None:
        resp = client.get("/api/v1/alerts?severity=BOGUS")
        assert resp.status_code == 400

    def test_alert_fields_present(self, client: TestClient) -> None:
        client.post("/api/v1/analyze/packets", json={"packets": _PACKET_DATA})
        alerts = client.get("/api/v1/alerts").json()
        if alerts:
            required = {"alert_id", "rule_id", "title", "severity", "source_ip", "evidence"}
            assert required.issubset(alerts[0].keys())


class TestAlertStats:
    def test_stats_returns_200(self, client: TestClient) -> None:
        resp = client.get("/api/v1/alerts/stats")
        assert resp.status_code == 200

    def test_stats_has_total(self, client: TestClient) -> None:
        data = client.get("/api/v1/alerts/stats").json()
        assert "total" in data

    def test_stats_total_zero_initially(self, client: TestClient) -> None:
        data = client.get("/api/v1/alerts/stats").json()
        assert data["total"] == 0
