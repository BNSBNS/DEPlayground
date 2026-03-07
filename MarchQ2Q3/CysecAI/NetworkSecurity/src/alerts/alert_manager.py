"""In-memory + SQLite alert manager with deduplication."""

from __future__ import annotations

import datetime
import json
from typing import Any

import aiosqlite

from src.models import AlertSeverity, NetworkAlert

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS alerts (
    alert_id TEXT PRIMARY KEY,
    rule_id TEXT NOT NULL,
    title TEXT NOT NULL,
    severity TEXT NOT NULL,
    mitre_technique_id TEXT NOT NULL,
    source_ip TEXT NOT NULL,
    dest_ip TEXT,
    timestamp TEXT NOT NULL,
    evidence TEXT NOT NULL,
    packet_count INTEGER NOT NULL DEFAULT 0,
    extra TEXT NOT NULL DEFAULT '{}'
)
"""

_INSERT = """
INSERT OR IGNORE INTO alerts
(alert_id, rule_id, title, severity, mitre_technique_id,
 source_ip, dest_ip, timestamp, evidence, packet_count, extra)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


class AlertManager:
    """Manages NetworkAlerts with SQLite persistence and in-memory deduplication."""

    def __init__(self, db_path: str = ":memory:") -> None:
        self._db_path = db_path
        # dedup key: (rule_id, source_ip) seen within current session
        self._seen: set[tuple[str, str]] = set()
        self._db: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        """Open a persistent connection and create tables."""
        self._db = await aiosqlite.connect(self._db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.execute(_CREATE_TABLE)
        await self._db.commit()

    async def close(self) -> None:
        """Close the database connection."""
        if self._db is not None:
            await self._db.close()
            self._db = None

    async def add_alert(self, alert: NetworkAlert) -> bool:
        """Store alert. Returns True if added (False if duplicate in session)."""
        assert self._db is not None, "AlertManager.initialize() must be called first"
        key = (alert.rule_id, alert.source_ip)
        if key in self._seen:
            return False
        self._seen.add(key)
        await self._db.execute(
            _INSERT,
            (
                alert.alert_id,
                alert.rule_id,
                alert.title,
                str(alert.severity),
                alert.mitre_technique_id,
                alert.source_ip,
                alert.dest_ip,
                alert.timestamp.isoformat(),
                alert.evidence,
                alert.packet_count,
                json.dumps(alert.extra),
            ),
        )
        await self._db.commit()
        return True

    async def add_alerts(self, alerts: list[NetworkAlert]) -> int:
        """Add multiple alerts. Returns count of newly added (non-duplicate) alerts."""
        added = 0
        for alert in alerts:
            if await self.add_alert(alert):
                added += 1
        return added

    async def get_alerts(
        self,
        severity: AlertSeverity | None = None,
        limit: int = 100,
    ) -> list[NetworkAlert]:
        """Retrieve stored alerts, optionally filtered by severity."""
        assert self._db is not None, "AlertManager.initialize() must be called first"
        if severity is not None:
            cursor = await self._db.execute(
                "SELECT * FROM alerts WHERE severity = ? ORDER BY timestamp DESC LIMIT ?",
                (str(severity), limit),
            )
        else:
            cursor = await self._db.execute(
                "SELECT * FROM alerts ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            )
        rows = await cursor.fetchall()
        return [_row_to_alert(dict(row)) for row in rows]

    async def get_stats(self) -> dict[str, Any]:
        """Return summary statistics."""
        assert self._db is not None, "AlertManager.initialize() must be called first"
        cursor = await self._db.execute(
            "SELECT severity, COUNT(*) as cnt FROM alerts GROUP BY severity"
        )
        rows = await cursor.fetchall()
        total_cursor = await self._db.execute("SELECT COUNT(*) FROM alerts")
        total_row = await total_cursor.fetchone()
        total = total_row[0] if total_row else 0
        by_severity: dict[str, int] = {row["severity"]: row["cnt"] for row in rows}
        return {"total": total, "by_severity": by_severity}


def _row_to_alert(row: dict[str, Any]) -> NetworkAlert:
    return NetworkAlert(
        alert_id=row["alert_id"],
        rule_id=row["rule_id"],
        title=row["title"],
        severity=AlertSeverity(row["severity"]),
        mitre_technique_id=row["mitre_technique_id"],
        source_ip=row["source_ip"],
        dest_ip=row.get("dest_ip"),
        timestamp=datetime.datetime.fromisoformat(row["timestamp"]),
        evidence=row["evidence"],
        packet_count=int(row.get("packet_count", 0)),
        extra=json.loads(row.get("extra", "{}")),
    )
