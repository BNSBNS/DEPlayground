"""Tests for the alert manager."""

from __future__ import annotations

import datetime

import pytest

from src.alerts.alert_manager import AlertManager
from src.models import AlertSeverity, NetworkAlert

_TS = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)


def _alert(rule_id: str = "port_scan", src_ip: str = "1.2.3.4") -> NetworkAlert:
    return NetworkAlert(
        rule_id=rule_id,
        title="Test Alert",
        severity=AlertSeverity.HIGH,
        mitre_technique_id="T1046",
        source_ip=src_ip,
        timestamp=_TS,
        evidence="Test evidence",
    )


@pytest.fixture()
async def manager() -> AlertManager:
    mgr = AlertManager(db_path=":memory:")
    await mgr.initialize()
    return mgr


class TestAlertManager:
    async def test_add_alert_returns_true(self, manager: AlertManager) -> None:
        added = await manager.add_alert(_alert())
        assert added is True

    async def test_duplicate_alert_returns_false(self, manager: AlertManager) -> None:
        await manager.add_alert(_alert())
        added_again = await manager.add_alert(_alert())
        assert added_again is False

    async def test_different_rule_not_duplicate(self, manager: AlertManager) -> None:
        await manager.add_alert(_alert("rule_a"))
        added = await manager.add_alert(_alert("rule_b"))
        assert added is True

    async def test_different_src_not_duplicate(self, manager: AlertManager) -> None:
        await manager.add_alert(_alert(src_ip="1.2.3.4"))
        added = await manager.add_alert(_alert(src_ip="5.6.7.8"))
        assert added is True

    async def test_get_alerts_returns_added(self, manager: AlertManager) -> None:
        await manager.add_alert(_alert())
        alerts = await manager.get_alerts()
        assert len(alerts) == 1

    async def test_get_alerts_filtered_by_severity(self, manager: AlertManager) -> None:
        high = _alert("rule_high")
        low = NetworkAlert(
            rule_id="rule_low",
            title="Low",
            severity=AlertSeverity.LOW,
            mitre_technique_id="T1046",
            source_ip="9.9.9.9",
            evidence="e",
        )
        await manager.add_alert(high)
        await manager.add_alert(low)
        high_alerts = await manager.get_alerts(severity=AlertSeverity.HIGH)
        assert all(a.severity == AlertSeverity.HIGH for a in high_alerts)

    async def test_get_stats_total(self, manager: AlertManager) -> None:
        await manager.add_alert(_alert("r1", "1.2.3.4"))
        await manager.add_alert(_alert("r2", "5.6.7.8"))
        stats = await manager.get_stats()
        assert stats["total"] == 2

    async def test_get_stats_by_severity(self, manager: AlertManager) -> None:
        await manager.add_alert(_alert())
        stats = await manager.get_stats()
        assert "HIGH" in stats["by_severity"]

    async def test_add_alerts_bulk(self, manager: AlertManager) -> None:
        alerts = [_alert(f"rule_{i}", f"10.0.0.{i}") for i in range(5)]
        count = await manager.add_alerts(alerts)
        assert count == 5

    async def test_add_alerts_dedup_in_bulk(self, manager: AlertManager) -> None:
        # Same rule + src twice = 1 added
        alerts = [_alert("same_rule", "1.2.3.4"), _alert("same_rule", "1.2.3.4")]
        count = await manager.add_alerts(alerts)
        assert count == 1

    async def test_empty_get(self, manager: AlertManager) -> None:
        alerts = await manager.get_alerts()
        assert alerts == []

    async def test_limit_respected(self, manager: AlertManager) -> None:
        for i in range(10):
            await manager.add_alert(_alert(f"rule_{i}", f"10.0.0.{i}"))
        alerts = await manager.get_alerts(limit=3)
        assert len(alerts) <= 3
