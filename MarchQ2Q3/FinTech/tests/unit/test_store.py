"""Tests for DuckDB-backed DataStore."""

from __future__ import annotations

import threading
from pathlib import Path

import pandas as pd
import pytest

from src.data.store import DataStore


@pytest.fixture
def store(tmp_path: Path) -> DataStore:
    """DataStore pointed at a temp directory."""
    return DataStore(data_dir=str(tmp_path))


@pytest.fixture
def sample_df() -> pd.DataFrame:
    """Small DataFrame for save/load tests."""
    return pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"]),
            "close": [185.0, 186.5, 184.2],
            "volume": [50_000_000, 60_000_000, 55_000_000],
        }
    )


class TestSaveLoad:
    def test_save_creates_parquet(self, store: DataStore, sample_df: pd.DataFrame) -> None:
        store.save(sample_df, "test_data")
        path = Path(store.data_dir) / "test_data.parquet"
        assert path.exists()

    def test_load_roundtrip(self, store: DataStore, sample_df: pd.DataFrame) -> None:
        store.save(sample_df, "test_data")
        loaded = store.load("test_data")
        pd.testing.assert_frame_equal(loaded, sample_df)

    def test_save_nested_name(self, store: DataStore, sample_df: pd.DataFrame) -> None:
        store.save(sample_df, "market_data/AAPL")
        path = Path(store.data_dir) / "market_data" / "AAPL.parquet"
        assert path.exists()

    def test_load_missing_raises(self, store: DataStore) -> None:
        with pytest.raises(FileNotFoundError, match="No data at"):
            store.load("nonexistent")


class TestQuery:
    def test_simple_sql(self, store: DataStore) -> None:
        result = store.query("SELECT 1 AS x")
        assert result.iloc[0]["x"] == 1

    def test_query_parquet(self, store: DataStore, sample_df: pd.DataFrame) -> None:
        store.save(sample_df, "prices")
        result = store.query_parquet("prices")
        assert len(result) == len(sample_df)

    def test_query_parquet_with_where(self, store: DataStore, sample_df: pd.DataFrame) -> None:
        store.save(sample_df, "prices")
        result = store.query_parquet("prices", sql_where="close > 185.0")
        assert len(result) == 1
        assert result.iloc[0]["close"] == 186.5

    def test_query_parquet_missing_raises(self, store: DataStore) -> None:
        with pytest.raises(FileNotFoundError, match="No data at"):
            store.query_parquet("nonexistent")


class TestThreadSafety:
    def test_connections_are_thread_local(self, store: DataStore) -> None:
        """Different threads get different connections."""
        connections: list[int] = []

        def get_conn_id() -> None:
            conn = store._conn()
            connections.append(id(conn))

        t1 = threading.Thread(target=get_conn_id)
        t2 = threading.Thread(target=get_conn_id)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert len(connections) == 2
        assert connections[0] != connections[1]

    def test_concurrent_reads(self, store: DataStore) -> None:
        """Multiple threads can read the same Parquet concurrently."""
        df = pd.DataFrame(
            {
                "date": pd.to_datetime(["2024-01-02"]),
                "value": [42.0],
            }
        )
        store.save(df, "shared")

        results: list[pd.DataFrame] = []
        errors: list[Exception] = []

        def read_data() -> None:
            try:
                results.append(store.load("shared"))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=read_data) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 4
        for r in results:
            assert r.iloc[0]["value"] == 42.0
