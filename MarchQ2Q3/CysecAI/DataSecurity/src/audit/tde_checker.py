"""TDE (Transparent Data Encryption) checker."""

from __future__ import annotations

from src.db.adapter import AbstractDBAdapter
from src.models import EncryptionStatus


def check_tde(adapter: AbstractDBAdapter) -> EncryptionStatus:
    """Check encryption-at-rest status for the given database connection.

    Returns an EncryptionStatus with tde_enabled and details.
    """
    tde_enabled, tde_details = adapter.check_tde()
    tls_enabled, tls_version, tls_cipher = adapter.check_tls()

    return EncryptionStatus(
        database_name=adapter.database_name(),
        tde_enabled=tde_enabled,
        tls_enabled=tls_enabled,
        tde_details=tde_details,
        tls_version=tls_version,
        tls_cipher=tls_cipher,
    )
