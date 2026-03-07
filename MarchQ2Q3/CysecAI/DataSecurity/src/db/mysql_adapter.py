"""MySQL database adapter."""

from __future__ import annotations

from sqlalchemy import Engine, create_engine, text

from src.db.adapter import AbstractDBAdapter


class MySQLAdapter(AbstractDBAdapter):
    """MySQL database adapter with TDE/TLS introspection."""

    def __init__(self, db_url: str) -> None:
        self._engine = create_engine(db_url, echo=False)

    @property
    def engine(self) -> Engine:
        return self._engine

    def check_tde(self) -> tuple[bool, str]:
        """Check MySQL InnoDB tablespace encryption (TDE)."""
        with self._engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT COUNT(*) FROM information_schema.INNODB_TABLESPACES "
                    "WHERE FLAG & 8192 > 0"
                )
            )
            row = result.fetchone()
            encrypted_count = int(row[0]) if row else 0

        if encrypted_count > 0:
            return True, f"{encrypted_count} encrypted InnoDB tablespace(s) found."
        return False, "No encrypted InnoDB tablespaces found."

    def check_tls(self) -> tuple[bool, str, str]:
        """Check if the MySQL connection uses SSL."""
        with self._engine.connect() as conn:
            result = conn.execute(text("SHOW STATUS LIKE 'Ssl_version'"))
            row = result.fetchone()
            if row and row[1]:
                version = str(row[1])
                cipher_result = conn.execute(text("SHOW STATUS LIKE 'Ssl_cipher'"))
                cipher_row = cipher_result.fetchone()
                cipher = str(cipher_row[1]) if cipher_row and cipher_row[1] else ""
                return True, version, cipher
        return False, "", ""

    def database_name(self) -> str:
        with self._engine.connect() as conn:
            result = conn.execute(text("SELECT DATABASE()"))
            row = result.fetchone()
            return str(row[0]) if row else "unknown"
