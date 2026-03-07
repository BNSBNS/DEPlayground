"""TLS connection checker."""

from __future__ import annotations

from src.db.adapter import AbstractDBAdapter
from src.models import EncryptionStatus


def check_tls(adapter: AbstractDBAdapter) -> EncryptionStatus:
    """Check TLS status for the database connection.

    Returns an EncryptionStatus populated with TLS details.
    """
    tls_enabled, tls_version, tls_cipher = adapter.check_tls()
    tde_enabled, tde_details = adapter.check_tde()

    return EncryptionStatus(
        database_name=adapter.database_name(),
        tde_enabled=tde_enabled,
        tls_enabled=tls_enabled,
        tde_details=tde_details,
        tls_version=tls_version,
        tls_cipher=tls_cipher,
    )


def is_tls_secure(status: EncryptionStatus) -> bool:
    """Return True if TLS version is TLSv1.2 or higher."""
    if not status.tls_enabled:
        return False
    version = status.tls_version.upper()
    # Accept TLSv1.2 and TLSv1.3
    return "1.2" in version or "1.3" in version
