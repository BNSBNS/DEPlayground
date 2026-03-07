"""SQLite-backed event and alert storage.

Stores normalized events and detection alerts for querying via API.
"""

from __future__ import annotations

import json
import sqlite3
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

    from src.ingestion.normalizer import NormalizedEvent
    from src.pipeline.processor import DetectionAlert


class EventStore:
    """SQLite storage for events and alerts."""

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                source TEXT NOT NULL,
                event_type TEXT NOT NULL,
                severity TEXT DEFAULT 'info',
                src_ip TEXT,
                dst_ip TEXT,
                user TEXT,
                action TEXT,
                hostname TEXT,
                details TEXT DEFAULT '{}'
            );
            CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
            CREATE INDEX IF NOT EXISTS idx_events_src_ip ON events(src_ip);
            CREATE INDEX IF NOT EXISTS idx_events_user ON events(user);

            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                alert_type TEXT NOT NULL,
                event_id TEXT,
                rule_id TEXT,
                rule_title TEXT,
                severity TEXT DEFAULT 'medium',
                src_ip TEXT,
                user TEXT,
                details TEXT DEFAULT '{}',
                FOREIGN KEY (event_id) REFERENCES events(event_id)
            );
            CREATE INDEX IF NOT EXISTS idx_alerts_timestamp ON alerts(timestamp);
            CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alerts(severity);
        """)

    def store_event(self, event: NormalizedEvent) -> None:
        """Insert a normalized event."""
        self._conn.execute(
            """INSERT OR IGNORE INTO events
               (event_id, timestamp, source, event_type, severity,
                src_ip, dst_ip, user, action, hostname, details)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                event.event_id,
                event.timestamp.isoformat(),
                event.source,
                event.event_type,
                event.severity,
                event.src_ip,
                event.dst_ip,
                event.user,
                event.action,
                event.hostname,
                json.dumps(event.details),
            ),
        )
        self._conn.commit()

    def store_alert(self, alert: DetectionAlert) -> None:
        """Insert a detection alert."""
        details = alert.to_dict()
        rule_id = details.get("rule_id", details.get("correlation_rule_id", ""))
        rule_title = details.get("rule_title", details.get("correlation_title", ""))
        severity = details.get("rule_severity", details.get("correlation_severity", "medium"))

        self._conn.execute(
            """INSERT INTO alerts
               (timestamp, alert_type, event_id, rule_id, rule_title,
                severity, src_ip, user, details)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                alert.event.timestamp.isoformat(),
                alert.alert_type,
                alert.event.event_id,
                rule_id,
                rule_title,
                severity,
                alert.event.src_ip,
                alert.event.user,
                json.dumps(details),
            ),
        )
        self._conn.commit()

    def query_events(
        self,
        src_ip: str | None = None,
        user: str | None = None,
        event_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Query events with optional filters."""
        conditions: list[str] = []
        params: list[str | int] = []
        if src_ip:
            conditions.append("src_ip = ?")
            params.append(src_ip)
        if user:
            conditions.append("user = ?")
            params.append(user)
        if event_type:
            conditions.append("event_type = ?")
            params.append(event_type)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        query = f"SELECT * FROM events {where} ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = self._conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def query_alerts(
        self,
        severity: str | None = None,
        rule_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Query alerts with optional filters."""
        conditions: list[str] = []
        params: list[str | int] = []
        if severity:
            conditions.append("severity = ?")
            params.append(severity)
        if rule_id:
            conditions.append("rule_id = ?")
            params.append(rule_id)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        query = f"SELECT * FROM alerts {where} ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = self._conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def get_stats(self) -> dict[str, int]:
        """Get storage statistics."""
        event_count: int = self._conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        alert_count: int = self._conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
        return {"event_count": event_count, "alert_count": alert_count}

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()
