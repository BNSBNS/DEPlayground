"""Tests for access logger (append-only audit log)."""

from __future__ import annotations

from src.audit.access_logger import AccessLogger, create_audit_logger
from src.models import AuditEvent, SuspiciousQueryType


class TestAccessLogger:
    def test_log_and_retrieve(self, db_session) -> None:  # type: ignore[no-untyped-def]
        logger = AccessLogger(db_session)
        event = AuditEvent(db_user="admin", query_text="SELECT 1")
        logger.log(event)
        events = logger.get_events()
        assert len(events) == 1
        assert events[0].db_user == "admin"

    def test_count_increments(self, db_session) -> None:  # type: ignore[no-untyped-def]
        logger = AccessLogger(db_session)
        assert logger.count() == 0
        logger.log(AuditEvent(db_user="u", query_text="SELECT 1"))
        assert logger.count() == 1
        logger.log(AuditEvent(db_user="u", query_text="SELECT 2"))
        assert logger.count() == 2

    def test_filter_suspicious_only(self, db_session) -> None:  # type: ignore[no-untyped-def]
        logger = AccessLogger(db_session)
        clean = AuditEvent(db_user="app", query_text="SELECT id FROM orders")
        suspicious = AuditEvent(
            db_user="hacker",
            query_text="SELECT * FROM users",
            is_suspicious=True,
            suspicious_reasons=[SuspiciousQueryType.PII_TABLE_WILDCARD],
        )
        logger.log(clean)
        logger.log(suspicious)
        suspicious_events = logger.get_events(suspicious_only=True)
        assert len(suspicious_events) == 1
        assert suspicious_events[0].db_user == "hacker"

    def test_is_append_only(self, db_session) -> None:  # type: ignore[no-untyped-def]
        logger = AccessLogger(db_session)
        assert logger.is_append_only()

    def test_event_roundtrip_preserves_fields(self, db_session) -> None:  # type: ignore[no-untyped-def]
        logger = AccessLogger(db_session)
        event = AuditEvent(
            db_user="analyst",
            query_text="SELECT * FROM products",
            tables_accessed=["products"],
            source_ip="10.0.0.5",
            row_count=500,
        )
        logger.log(event)
        retrieved = logger.get_events()
        assert retrieved[0].db_user == "analyst"
        assert retrieved[0].source_ip == "10.0.0.5"
        assert retrieved[0].row_count == 500


class TestCreateAuditLogger:
    def test_create_with_enforcement(self, db_session) -> None:  # type: ignore[no-untyped-def]
        logger = create_audit_logger(db_session, enforce_immutability=True)
        assert logger.is_append_only()

    def test_create_without_enforcement(self, db_session) -> None:  # type: ignore[no-untyped-def]
        logger = create_audit_logger(db_session, enforce_immutability=False)
        assert logger.is_append_only()
