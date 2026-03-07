"""Tests for TDE and TLS checking."""

from __future__ import annotations

from src.audit.tde_checker import check_tde
from src.audit.tls_checker import check_tls, is_tls_secure
from src.models import EncryptionStatus


class TestTDEChecker:
    def test_sqlite_tde_disabled(self, sqlite_adapter) -> None:  # type: ignore[no-untyped-def]
        status = check_tde(sqlite_adapter)
        assert not status.tde_enabled
        assert "SQLite" in status.tde_details

    def test_returns_encryption_status(self, sqlite_adapter) -> None:  # type: ignore[no-untyped-def]
        status = check_tde(sqlite_adapter)
        assert isinstance(status, EncryptionStatus)

    def test_database_name_set(self, sqlite_adapter) -> None:  # type: ignore[no-untyped-def]
        status = check_tde(sqlite_adapter)
        assert status.database_name == ":memory:"


class TestTLSChecker:
    def test_sqlite_tls_disabled(self, sqlite_adapter) -> None:  # type: ignore[no-untyped-def]
        status = check_tls(sqlite_adapter)
        assert not status.tls_enabled

    def test_is_tls_secure_off(self) -> None:
        status = EncryptionStatus(database_name="db", tls_enabled=False)
        assert not is_tls_secure(status)

    def test_is_tls_secure_v13(self) -> None:
        status = EncryptionStatus(database_name="db", tls_enabled=True, tls_version="TLSv1.3")
        assert is_tls_secure(status)

    def test_is_tls_secure_v12(self) -> None:
        status = EncryptionStatus(database_name="db", tls_enabled=True, tls_version="TLSv1.2")
        assert is_tls_secure(status)

    def test_is_tls_secure_v10_insecure(self) -> None:
        status = EncryptionStatus(database_name="db", tls_enabled=True, tls_version="TLSv1.0")
        assert not is_tls_secure(status)
