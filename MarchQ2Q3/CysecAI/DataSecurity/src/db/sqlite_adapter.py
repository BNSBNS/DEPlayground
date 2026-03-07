"""SQLite adapter — used for local testing and development."""

from __future__ import annotations

from sqlalchemy import Engine, create_engine

from src.db.adapter import AbstractDBAdapter


class SQLiteAdapter(AbstractDBAdapter):
    """SQLite database adapter for testing and offline use."""

    def __init__(self, db_url: str = "sqlite:///:memory:") -> None:
        self._engine = create_engine(db_url, echo=False)

    @property
    def engine(self) -> Engine:
        return self._engine

    def check_tde(self) -> tuple[bool, str]:
        """SQLite does not support TDE."""
        return False, "SQLite does not support transparent data encryption."

    def check_tls(self) -> tuple[bool, str, str]:
        """SQLite uses file-based access, no network TLS."""
        return False, "", ""

    def database_name(self) -> str:
        url = str(self._engine.url)
        if ":memory:" in url:
            return ":memory:"
        # Extract filename from path
        return url.rsplit("/", maxsplit=1)[-1].replace(".db", "")
