"""Tests for suspicious query detection."""

from __future__ import annotations

import datetime

from src.audit.query_analyzer import analyze_event, analyze_query
from src.models import AuditEvent, SuspiciousQueryType


class TestAnalyzeQuery:
    def test_clean_query_not_suspicious(self) -> None:
        result = analyze_query("SELECT id, name FROM orders WHERE id = 1")
        assert result == []

    def test_bulk_select_by_row_count(self) -> None:
        result = analyze_query("SELECT * FROM users", row_count=15000)
        assert SuspiciousQueryType.BULK_SELECT in result

    def test_bulk_select_no_limit_no_where(self) -> None:
        result = analyze_query("SELECT * FROM orders")
        assert SuspiciousQueryType.BULK_SELECT in result

    def test_limited_select_not_bulk(self) -> None:
        result = analyze_query("SELECT * FROM users LIMIT 10")
        assert SuspiciousQueryType.BULK_SELECT not in result

    def test_schema_dump_information_schema(self) -> None:
        result = analyze_query("SELECT * FROM information_schema.tables")
        assert SuspiciousQueryType.SCHEMA_DUMP in result

    def test_schema_dump_show_tables(self) -> None:
        result = analyze_query("show tables")
        assert SuspiciousQueryType.SCHEMA_DUMP in result

    def test_pii_wildcard_users(self) -> None:
        result = analyze_query("SELECT * FROM users")
        assert SuspiciousQueryType.PII_TABLE_WILDCARD in result

    def test_pii_wildcard_customers(self) -> None:
        result = analyze_query("SELECT * FROM customers")
        assert SuspiciousQueryType.PII_TABLE_WILDCARD in result

    def test_non_pii_table_wildcard_not_flagged(self) -> None:
        result = analyze_query("SELECT * FROM products")
        assert SuspiciousQueryType.PII_TABLE_WILDCARD not in result

    def test_off_hours_flagged(self) -> None:
        midnight = datetime.datetime(2026, 1, 1, 23, 30, tzinfo=datetime.UTC)
        result = analyze_query("SELECT 1", timestamp=midnight)
        assert SuspiciousQueryType.OFF_HOURS in result

    def test_business_hours_not_flagged(self) -> None:
        noon = datetime.datetime(2026, 1, 1, 12, 0, tzinfo=datetime.UTC)
        result = analyze_query("SELECT 1", timestamp=noon)
        assert SuspiciousQueryType.OFF_HOURS not in result

    def test_early_morning_is_off_hours(self) -> None:
        early = datetime.datetime(2026, 1, 1, 3, 0, tzinfo=datetime.UTC)
        result = analyze_query("SELECT 1", timestamp=early)
        assert SuspiciousQueryType.OFF_HOURS in result


class TestAnalyzeEvent:
    def test_clean_event_not_suspicious(self) -> None:
        event = AuditEvent(db_user="app", query_text="SELECT id FROM products WHERE id = 5")
        result = analyze_event(event)
        assert not result.is_suspicious

    def test_suspicious_query_flagged(self) -> None:
        event = AuditEvent(db_user="admin", query_text="SELECT * FROM users")
        result = analyze_event(event)
        assert result.is_suspicious
        assert SuspiciousQueryType.PII_TABLE_WILDCARD in result.suspicious_reasons

    def test_event_immutable_original(self) -> None:
        event = AuditEvent(db_user="admin", query_text="SELECT * FROM users")
        result = analyze_event(event)
        # Original event unchanged
        assert not event.is_suspicious
        assert result.is_suspicious
