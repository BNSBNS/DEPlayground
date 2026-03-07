"""PostgreSQL database adapter."""

from __future__ import annotations

from sqlalchemy import Engine, create_engine, text

from src.db.adapter import AbstractDBAdapter


class PostgreSQLAdapter(AbstractDBAdapter):
    """PostgreSQL database adapter with TDE/TLS introspection."""

    def __init__(self, db_url: str) -> None:
        self._engine = create_engine(db_url, echo=False)

    @property
    def engine(self) -> Engine:
        return self._engine

    def check_tde(self) -> tuple[bool, str]:
        """Check PostgreSQL encryption-at-rest (pgcrypto extension or tablespace encryption).

        Note: Standard PostgreSQL does not support native TDE. Check for
        pg_transparent_data_encryption extension or filesystem-level encryption.
        """
        with self._engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT extname FROM pg_extension WHERE extname IN "
                    "('pg_tde', 'pgcrypto', 'pg_transparent_data_encryption')"
                )
            )
            extensions = [row[0] for row in result]
        if extensions:
            return True, f"Extensions: {', '.join(extensions)}"
        return False, "No TDE extension found. Consider filesystem-level encryption (LUKS)."

    def check_tls(self) -> tuple[bool, str, str]:
        """Check if the current PostgreSQL connection uses SSL."""
        with self._engine.connect() as conn:
            ssl_result = conn.execute(text("SHOW ssl"))
            ssl_row = ssl_result.fetchone()
            ssl_on = ssl_row is not None and str(ssl_row[0]).lower() == "on"

            if ssl_on:
                try:
                    ver_result = conn.execute(text("SHOW ssl_min_protocol_version"))
                    ver_row = ver_result.fetchone()
                    version = str(ver_row[0]) if ver_row else "TLSv1.2"
                except Exception:
                    version = "TLS"
                return True, version, ""
        return False, "", ""

    def database_name(self) -> str:
        with self._engine.connect() as conn:
            result = conn.execute(text("SELECT current_database()"))
            row = result.fetchone()
            return str(row[0]) if row else "unknown"
