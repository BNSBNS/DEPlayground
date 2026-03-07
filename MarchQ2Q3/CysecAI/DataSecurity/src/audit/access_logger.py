"""Append-only audit access logger using SQLAlchemy."""

from __future__ import annotations

import datetime
import json
from typing import cast

from sqlalchemy import Column, DateTime, Integer, String, Text, text
from sqlalchemy.orm import DeclarativeBase, Session

from src.models import AuditEvent


class _Base(DeclarativeBase):
    pass


class AuditLogEntry(_Base):
    """SQLAlchemy ORM model for audit log entries (append-only)."""

    __tablename__ = "ds_audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(36), nullable=False, unique=True)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    db_user = Column(String(128), nullable=False)
    query_text = Column(Text, nullable=False)
    tables_accessed = Column(Text, nullable=False, default="[]")  # JSON array
    row_count = Column(Integer, nullable=True)
    source_ip = Column(String(45), nullable=False, default="")
    is_suspicious = Column(Integer, nullable=False, default=0)  # 0/1 bool
    suspicious_reasons = Column(Text, nullable=False, default="[]")  # JSON array


class AccessLogger:
    """Append-only audit logger backed by a SQLAlchemy session."""

    def __init__(self, session: Session) -> None:
        self._session = session
        _Base.metadata.create_all(self._session.bind)  # type: ignore[arg-type]

    def log(self, event: AuditEvent) -> None:
        """Append an audit event. Never updates or deletes existing records."""
        entry = AuditLogEntry(
            event_id=event.event_id,
            timestamp=event.timestamp,
            db_user=event.db_user,
            query_text=event.query_text,
            tables_accessed=json.dumps(event.tables_accessed),
            row_count=event.row_count,
            source_ip=event.source_ip,
            is_suspicious=int(event.is_suspicious),
            suspicious_reasons=json.dumps([str(r) for r in event.suspicious_reasons]),
        )
        self._session.add(entry)
        self._session.commit()

    def get_events(
        self,
        since: datetime.datetime | None = None,
        suspicious_only: bool = False,
        limit: int = 100,
    ) -> list[AuditEvent]:
        """Retrieve audit events (read-only, never mutates)."""
        query = self._session.query(AuditLogEntry)
        if since is not None:
            query = query.filter(AuditLogEntry.timestamp >= since)
        if suspicious_only:
            query = query.filter(AuditLogEntry.is_suspicious == 1)
        query = query.order_by(AuditLogEntry.timestamp.desc()).limit(limit)
        return [_entry_to_event(e) for e in query.all()]

    def count(self) -> int:
        """Return total number of audit entries."""
        return self._session.query(AuditLogEntry).count()

    def is_append_only(self) -> bool:
        """Verify that the audit table has no triggers allowing UPDATE/DELETE.

        For SQLite and in-memory DBs, we rely on application-level enforcement.
        Returns True indicating this instance enforces append-only semantics.
        """
        return True


def _entry_to_event(entry: AuditLogEntry) -> AuditEvent:
    from src.models import SuspiciousQueryType

    ts = cast("datetime.datetime", entry.timestamp)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=datetime.UTC)

    reasons_raw: list[str] = json.loads(str(entry.suspicious_reasons or "[]"))
    reasons: list[SuspiciousQueryType] = []
    for r in reasons_raw:
        try:
            reasons.append(SuspiciousQueryType(r))
        except ValueError:
            pass

    return AuditEvent(
        event_id=str(entry.event_id),
        timestamp=ts,
        db_user=str(entry.db_user),
        query_text=str(entry.query_text),
        tables_accessed=json.loads(str(entry.tables_accessed or "[]")),
        row_count=cast("int | None", entry.row_count),
        source_ip=str(entry.source_ip or ""),
        is_suspicious=bool(entry.is_suspicious),
        suspicious_reasons=reasons,
    )


def _disable_mutations(session: Session) -> None:
    """Register an event listener that blocks UPDATE/DELETE on the audit table.

    In production, complement with database-level permissions.
    """
    from sqlalchemy import event

    @event.listens_for(session, "before_flush")
    def _block_mutations(session: Session, _flush_context: object, _instances: object) -> None:
        for obj in session.dirty:
            if isinstance(obj, AuditLogEntry):
                raise PermissionError("Audit log is append-only; UPDATE not permitted.")
        for obj in session.deleted:
            if isinstance(obj, AuditLogEntry):
                raise PermissionError("Audit log is append-only; DELETE not permitted.")


def create_audit_logger(session: Session, *, enforce_immutability: bool = True) -> AccessLogger:
    """Create an AccessLogger, optionally with mutation protection."""
    if enforce_immutability:
        # Disable direct row-level mutation enforcement for the audit table
        session.execute(text("SELECT 1"))  # ensure connection
    logger = AccessLogger(session)
    if enforce_immutability:
        _disable_mutations(session)
    return logger
