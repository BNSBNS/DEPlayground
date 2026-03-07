"""Tests for key manager."""

from __future__ import annotations

import pytest

from src.protection.key_manager import KeyManager, fingerprint_key


class TestKeyManager:
    def test_register_key(self) -> None:
        km = KeyManager()
        record = km.register_key("col-encryption", "column_encryption")
        assert record.name == "col-encryption"
        assert record.is_active

    def test_get_all_keys(self) -> None:
        km = KeyManager()
        km.register_key("k1", "tde")
        km.register_key("k2", "backup")
        assert len(km.get_all_keys()) == 2

    def test_rotate_key(self) -> None:
        km = KeyManager()
        key = km.register_key("k1", "tde", rotation_interval_days=1)
        rotated = km.rotate_key(key.key_id, new_key_hash="abc123")
        assert rotated.key_fingerprint == "abc123"

    def test_rotate_nonexistent_raises(self) -> None:
        km = KeyManager()
        with pytest.raises(KeyError):
            km.rotate_key("nonexistent-id")

    def test_deactivate_key(self) -> None:
        km = KeyManager()
        key = km.register_key("k1", "tde")
        km.deactivate_key(key.key_id)
        updated = next(k for k in km.get_all_keys() if k.key_id == key.key_id)
        assert not updated.is_active

    def test_deactivate_nonexistent_raises(self) -> None:
        km = KeyManager()
        with pytest.raises(KeyError):
            km.deactivate_key("no-such-key")

    def test_overdue_keys(self) -> None:
        km = KeyManager()
        # Register a key with 0-day rotation interval (immediately overdue)
        km.register_key("old-key", "tde", rotation_interval_days=0)
        overdue = km.get_overdue_keys()
        assert len(overdue) == 1

    def test_not_overdue_within_window(self) -> None:
        km = KeyManager()
        km.register_key("fresh-key", "tde", rotation_interval_days=365)
        assert len(km.get_overdue_keys()) == 0

    def test_audit_report_structure(self) -> None:
        km = KeyManager()
        km.register_key("k1", "tde")
        report = km.audit_report()
        assert "total_keys" in report
        assert "overdue_rotations" in report
        assert "compliant" in report

    def test_audit_report_compliant_when_no_overdue(self) -> None:
        km = KeyManager()
        km.register_key("k1", "tde", rotation_interval_days=90)
        report = km.audit_report()
        assert report["compliant"]


class TestFingerprintKey:
    def test_returns_hex_string(self) -> None:
        fp = fingerprint_key(b"secret-key-material")
        assert len(fp) == 64  # SHA-256 hex = 64 chars
        assert all(c in "0123456789abcdef" for c in fp)

    def test_deterministic(self) -> None:
        assert fingerprint_key(b"abc") == fingerprint_key(b"abc")

    def test_different_keys_different_fingerprints(self) -> None:
        assert fingerprint_key(b"key1") != fingerprint_key(b"key2")
