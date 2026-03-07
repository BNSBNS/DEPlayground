"""Tests for the alert emitter."""

from __future__ import annotations

import datetime
import json
import pathlib
import tempfile

from src.alerts.emitter import emit
from src.models import AlertSeverity, NetworkAlert

_TS = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)


def _alert(rule_id: str = "port_scan") -> NetworkAlert:
    return NetworkAlert(
        rule_id=rule_id,
        title="Test Alert",
        severity=AlertSeverity.HIGH,
        mitre_technique_id="T1046",
        source_ip="1.2.3.4",
        timestamp=_TS,
        evidence="Test evidence",
    )


class TestEmit:
    def test_returns_count(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / "alerts.json"
            count = emit([_alert(), _alert("brute_force")], path)
            assert count == 2

    def test_creates_file(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / "alerts.json"
            emit([_alert()], path)
            assert path.exists()

    def test_json_readable(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / "alerts.json"
            emit([_alert()], path)
            data = json.loads(path.read_text(encoding="utf-8"))
            assert isinstance(data, list)
            assert len(data) == 1

    def test_fields_present(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / "alerts.json"
            emit([_alert()], path)
            data = json.loads(path.read_text(encoding="utf-8"))
            required = {
                "alert_id",
                "rule_id",
                "title",
                "severity",
                "source_ip",
                "evidence",
                "timestamp",
            }
            assert required.issubset(data[0].keys())

    def test_empty_alerts(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / "alerts.json"
            count = emit([], path)
            assert count == 0
            data = json.loads(path.read_text(encoding="utf-8"))
            assert data == []

    def test_creates_parent_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / "sub" / "dir" / "alerts.json"
            emit([_alert()], path)
            assert path.exists()

    def test_severity_as_string(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / "alerts.json"
            emit([_alert()], path)
            data = json.loads(path.read_text(encoding="utf-8"))
            assert data[0]["severity"] == "HIGH"
