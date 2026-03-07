"""Tests for the FastAPI REST API."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.main import app, set_state
from src.detection.rule_engine import RuleMatch
from src.detection.sigma_loader import SigmaCondition, SigmaDetection, SigmaRule
from src.ingestion.normalizer import NormalizedEvent
from src.pipeline.processor import DetectionAlert, EventProcessor
from src.storage.event_store import EventStore


@pytest.fixture()
def store() -> EventStore:
    return EventStore(":memory:")


@pytest.fixture()
def processor() -> EventProcessor:
    return EventProcessor(correlation_rules=[])


@pytest.fixture()
def _inject_state(store: EventStore, processor: EventProcessor) -> None:
    set_state(store=store, processor=processor)


@pytest.fixture()
async def client(_inject_state: None) -> AsyncClient:
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


def _make_event(event_id: str = "evt-api-001", **kwargs: object) -> NormalizedEvent:
    defaults = {
        "event_id": event_id,
        "timestamp": datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
        "source": "auth",
        "event_type": "login_failure",
        "severity": "warning",
        "src_ip": "10.0.0.1",
        "user": "admin",
    }
    defaults.update(kwargs)
    return NormalizedEvent(**defaults)  # type: ignore[arg-type]


# --- Health ---


class TestHealth:
    async def test_health(self, client: AsyncClient) -> None:
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


# --- Events ---


class TestEvents:
    async def test_get_events_empty(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/events")
        data = resp.json()
        assert resp.status_code == 200
        assert data["events"] == []
        assert data["count"] == 0

    async def test_get_events_with_data(self, client: AsyncClient, store: EventStore) -> None:
        store.store_event(_make_event())
        resp = await client.get("/api/v1/events")
        data = resp.json()
        assert data["count"] == 1
        assert data["events"][0]["event_id"] == "evt-api-001"

    async def test_filter_by_src_ip(self, client: AsyncClient, store: EventStore) -> None:
        store.store_event(_make_event("evt-1", src_ip="10.0.0.1"))
        store.store_event(_make_event("evt-2", src_ip="192.168.1.1"))
        resp = await client.get("/api/v1/events", params={"src_ip": "10.0.0.1"})
        data = resp.json()
        assert data["count"] == 1

    async def test_filter_by_user(self, client: AsyncClient, store: EventStore) -> None:
        store.store_event(_make_event("evt-1", user="admin"))
        store.store_event(_make_event("evt-2", user="guest"))
        resp = await client.get("/api/v1/events", params={"user": "admin"})
        assert resp.json()["count"] == 1

    async def test_pagination(self, client: AsyncClient, store: EventStore) -> None:
        for i in range(5):
            store.store_event(_make_event(f"evt-{i}"))
        resp = await client.get("/api/v1/events", params={"limit": 2})
        assert resp.json()["count"] == 2


# --- Alerts ---


class TestAlerts:
    async def test_get_alerts_empty(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/alerts")
        assert resp.status_code == 200
        assert resp.json()["count"] == 0

    async def test_get_alerts_with_data(self, client: AsyncClient, store: EventStore) -> None:
        event = _make_event()
        store.store_event(event)
        rule = SigmaRule(
            id="sigma-api-001",
            title="API Test Rule",
            level="high",
            detection=SigmaDetection(
                selections={
                    "sel": [
                        SigmaCondition(field="event_type", modifier="equals", value="login_failure")
                    ]
                },
                condition="sel",
            ),
        )
        match = RuleMatch(rule=rule, event=event, matched_fields={})
        alert = DetectionAlert(alert_type="rule", event=event, rule_match=match)
        store.store_alert(alert)

        resp = await client.get("/api/v1/alerts")
        data = resp.json()
        assert data["count"] == 1
        assert data["alerts"][0]["rule_id"] == "sigma-api-001"

    async def test_filter_alerts_by_severity(self, client: AsyncClient, store: EventStore) -> None:
        event = _make_event()
        store.store_event(event)
        rule = SigmaRule(
            id="sigma-api-002",
            title="High Sev Rule",
            level="high",
            detection=SigmaDetection(
                selections={
                    "sel": [SigmaCondition(field="event_type", modifier="equals", value="x")]
                },
                condition="sel",
            ),
        )
        match = RuleMatch(rule=rule, event=event, matched_fields={})
        alert = DetectionAlert(alert_type="rule", event=event, rule_match=match)
        store.store_alert(alert)

        resp = await client.get("/api/v1/alerts", params={"severity": "high"})
        assert resp.json()["count"] == 1

        resp = await client.get("/api/v1/alerts", params={"severity": "low"})
        assert resp.json()["count"] == 0


# --- Rules ---


class TestRules:
    async def test_get_rules(self, client: AsyncClient, processor: EventProcessor) -> None:
        rule = SigmaRule(
            id="sigma-api-r01",
            title="Rule for list",
            level="medium",
            tags=["attack.t1110"],
            mitre_technique_ids=["T1110"],
            detection=SigmaDetection(
                selections={"sel": [SigmaCondition(field="x", modifier="equals", value="y")]},
                condition="sel",
            ),
        )
        processor.rule_engine.add_rule(rule)
        resp = await client.get("/api/v1/rules")
        data = resp.json()
        assert data["count"] == 1
        assert data["rules"][0]["id"] == "sigma-api-r01"

    async def test_add_rule_via_post(self, client: AsyncClient) -> None:
        yaml_content = """
id: sigma-post-001
title: Posted Rule
level: high
tags:
  - attack.t1078
detection:
  selection:
    event_type|equals: login_failure
  condition: selection
"""
        resp = await client.post("/api/v1/rules", json={"yaml_content": yaml_content})
        assert resp.status_code == 200
        assert resp.json()["rule_id"] == "sigma-post-001"


# --- Stats ---


class TestStats:
    async def test_get_stats(self, client: AsyncClient, store: EventStore) -> None:
        store.store_event(_make_event())
        resp = await client.get("/api/v1/stats")
        data = resp.json()
        assert data["storage"]["event_count"] == 1
        assert "pipeline" in data
        assert "sigma_rules_loaded" in data
