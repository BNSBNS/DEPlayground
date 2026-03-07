"""Tests for schema scanner."""

from __future__ import annotations

from src.discovery.schema_scanner import scan_schema
from src.models import DataClassification


class TestScanSchema:
    def test_finds_all_tables(self, sqlite_adapter) -> None:  # type: ignore[no-untyped-def]
        tables = scan_schema(sqlite_adapter)
        table_names = {t.table_name for t in tables}
        assert "users" in table_names
        assert "payments" in table_names
        assert "health_records" in table_names

    def test_detects_email_column(self, sqlite_adapter) -> None:  # type: ignore[no-untyped-def]
        tables = scan_schema(sqlite_adapter)
        users = next(t for t in tables if t.table_name == "users")
        email_col = next((c for c in users.columns if c.column_name == "email"), None)
        assert email_col is not None
        assert email_col.classification != DataClassification.PUBLIC

    def test_detects_credit_card_as_pci(self, sqlite_adapter) -> None:  # type: ignore[no-untyped-def]
        tables = scan_schema(sqlite_adapter)
        payments = next(t for t in tables if t.table_name == "payments")
        cc_col = next((c for c in payments.columns if c.column_name == "credit_card"), None)
        assert cc_col is not None
        assert cc_col.classification == DataClassification.PCI

    def test_event_logs_no_pii(self, sqlite_adapter) -> None:  # type: ignore[no-untyped-def]
        tables = scan_schema(sqlite_adapter)
        logs = next(t for t in tables if t.table_name == "event_logs")
        assert not logs.has_pii

    def test_health_records_has_pii(self, sqlite_adapter) -> None:  # type: ignore[no-untyped-def]
        tables = scan_schema(sqlite_adapter)
        health = next(t for t in tables if t.table_name == "health_records")
        assert health.has_pii

    def test_column_data_types_present(self, sqlite_adapter) -> None:  # type: ignore[no-untyped-def]
        tables = scan_schema(sqlite_adapter)
        users = next(t for t in tables if t.table_name == "users")
        for col in users.columns:
            assert col.data_type  # non-empty type string
