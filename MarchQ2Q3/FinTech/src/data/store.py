"""DuckDB-backed data store over Parquet files.

Thread-safe via thread-local connections (DuckDB is not thread-safe).
"""

from __future__ import annotations

import threading
from pathlib import Path

import duckdb
import pandas as pd


class DataStore:
    """Read/write data as Parquet with DuckDB SQL query support."""

    _local = threading.local()

    def __init__(self, data_dir: str = "data/processed") -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _conn(self) -> duckdb.DuckDBPyConnection:
        """Get a thread-local DuckDB connection."""
        if not hasattr(self._local, "conn"):
            self._local.conn = duckdb.connect()
        return self._local.conn

    def query(self, sql: str, params: dict | None = None) -> pd.DataFrame:
        """Execute a SQL query and return results as DataFrame."""
        return self._conn().execute(sql, params or {}).fetchdf()

    def save(self, df: pd.DataFrame, name: str) -> None:
        """Save DataFrame as Parquet file."""
        path = self.data_dir / f"{name}.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(path, index=False)

    def load(self, name: str) -> pd.DataFrame:
        """Load a Parquet file as DataFrame."""
        path = self.data_dir / f"{name}.parquet"
        if not path.exists():
            raise FileNotFoundError(f"No data at {path}")
        return pd.read_parquet(path)

    def query_parquet(self, name: str, sql_where: str = "") -> pd.DataFrame:
        """Query a Parquet file directly with DuckDB SQL."""
        path = self.data_dir / f"{name}.parquet"
        if not path.exists():
            raise FileNotFoundError(f"No data at {path}")
        sql = f"SELECT * FROM read_parquet('{path}')"
        if sql_where:
            sql += f" WHERE {sql_where}"
        return self._conn().execute(sql).fetchdf()
