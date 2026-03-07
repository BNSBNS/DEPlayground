"""Abstract database adapter interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, cast

from sqlalchemy import Engine, inspect
from sqlalchemy.engine import Inspector


class AbstractDBAdapter(ABC):
    """Abstract interface for database-specific operations."""

    @property
    @abstractmethod
    def engine(self) -> Engine:
        """Return the underlying SQLAlchemy engine."""

    @property
    def inspector(self) -> Inspector:
        """Return a SQLAlchemy Inspector for schema introspection."""
        return inspect(self.engine)

    def get_table_names(self) -> list[str]:
        """Return all table names in the current schema."""
        return self.inspector.get_table_names()

    def get_columns(self, table_name: str) -> list[dict[str, Any]]:
        """Return column metadata for a table."""
        return cast("list[dict[str, Any]]", self.inspector.get_columns(table_name))

    @abstractmethod
    def check_tde(self) -> tuple[bool, str]:
        """Check if Transparent Data Encryption is enabled.

        Returns (enabled, details_string).
        """

    @abstractmethod
    def check_tls(self) -> tuple[bool, str, str]:
        """Check if the connection uses TLS.

        Returns (enabled, version_string, cipher_string).
        """

    @abstractmethod
    def database_name(self) -> str:
        """Return the name of the connected database."""
