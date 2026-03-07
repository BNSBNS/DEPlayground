"""Key rotation tracking and access policy audit."""

from __future__ import annotations

import datetime
import hashlib
import uuid
from typing import Any

from pydantic import BaseModel, Field


class KeyRecord(BaseModel):
    """Record of an encryption key lifecycle."""

    key_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    purpose: str  # e.g., "column_encryption", "backup", "tde"
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(tz=datetime.UTC)
    )
    last_rotated: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(tz=datetime.UTC)
    )
    rotation_interval_days: int = 90
    is_active: bool = True
    key_fingerprint: str = ""  # SHA-256 of key material, never the key itself

    @property
    def days_since_rotation(self) -> int:
        delta = datetime.datetime.now(tz=datetime.UTC) - self.last_rotated
        return delta.days

    @property
    def rotation_overdue(self) -> bool:
        return self.days_since_rotation >= self.rotation_interval_days

    @property
    def days_until_rotation(self) -> int:
        return max(0, self.rotation_interval_days - self.days_since_rotation)


class KeyManager:
    """In-memory key rotation tracking.

    In production, integrate with AWS KMS, HashiCorp Vault, or Azure Key Vault.
    This implementation tracks metadata only — never stores actual key material.
    """

    def __init__(self) -> None:
        self._keys: dict[str, KeyRecord] = {}

    def register_key(
        self,
        name: str,
        purpose: str,
        rotation_interval_days: int = 90,
        key_material_hash: str = "",
    ) -> KeyRecord:
        """Register a key by metadata (never store actual key material)."""
        record = KeyRecord(
            name=name,
            purpose=purpose,
            rotation_interval_days=rotation_interval_days,
            key_fingerprint=key_material_hash,
        )
        self._keys[record.key_id] = record
        return record

    def rotate_key(self, key_id: str, new_key_hash: str = "") -> KeyRecord:
        """Mark a key as rotated."""
        if key_id not in self._keys:
            raise KeyError(f"Key {key_id!r} not found.")
        old = self._keys[key_id]
        rotated = old.model_copy(
            update={
                "last_rotated": datetime.datetime.now(tz=datetime.UTC),
                "key_fingerprint": new_key_hash,
            }
        )
        self._keys[key_id] = rotated
        return rotated

    def deactivate_key(self, key_id: str) -> None:
        """Deactivate a key (mark as inactive)."""
        if key_id not in self._keys:
            raise KeyError(f"Key {key_id!r} not found.")
        self._keys[key_id] = self._keys[key_id].model_copy(update={"is_active": False})

    def get_overdue_keys(self) -> list[KeyRecord]:
        """Return keys whose rotation is overdue."""
        return [k for k in self._keys.values() if k.is_active and k.rotation_overdue]

    def get_all_keys(self) -> list[KeyRecord]:
        """Return all registered key records."""
        return list(self._keys.values())

    def audit_report(self) -> dict[str, Any]:
        """Produce a key management audit summary."""
        all_keys = self.get_all_keys()
        overdue = self.get_overdue_keys()
        return {
            "total_keys": len(all_keys),
            "active_keys": sum(1 for k in all_keys if k.is_active),
            "overdue_rotations": len(overdue),
            "overdue_key_ids": [k.key_id for k in overdue],
            "compliant": len(overdue) == 0,
        }


def fingerprint_key(key_bytes: bytes) -> str:
    """Compute a SHA-256 fingerprint of key material (for registration only).

    Never store the actual key bytes — only the fingerprint.
    """
    return hashlib.sha256(key_bytes).hexdigest()
