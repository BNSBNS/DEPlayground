"""Integration tests for API endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.api.main import create_app
from src.config import get_settings

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def mock_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Set up mock data for API tests."""
    market_dir = tmp_path / "mock" / "market_data"
    market_dir.mkdir(parents=True)
    rng = np.random.default_rng(42)
    dates = pd.bdate_range("2024-01-02", periods=60)
    closes = 185.0 + np.cumsum(rng.normal(0, 1.5, 60))
    ohlcv = pd.DataFrame(
        {
            "date": pd.to_datetime(dates),
            "open": closes - rng.uniform(0, 1, 60),
            "high": closes + rng.uniform(0.5, 2, 60),
            "low": closes - rng.uniform(0.5, 2, 60),
            "close": closes,
            "volume": rng.integers(50_000_000, 100_000_000, 60),
        }
    )
    ohlcv.to_parquet(market_dir / "AAPL.parquet", index=False)

    options_dir = tmp_path / "mock" / "options_chains"
    options_dir.mkdir(parents=True)
    rows = []
    for K in np.arange(170.0, 200.0, 5.0):
        for opt_type in ["call", "put"]:
            rows.append(
                {
                    "ticker": "AAPL",
                    "date": "2024-01-15",
                    "expiration": "2024-02-16",
                    "strike": K,
                    "option_type": opt_type,
                    "bid": 1.0,
                    "ask": 1.5,
                    "last": 1.25,
                    "volume": 100,
                    "open_interest": 500,
                    "implied_vol": 0.25,
                }
            )
    pd.DataFrame(rows).to_parquet(options_dir / "AAPL.parquet", index=False)

    embeddings_dir = tmp_path / "embeddings"
    embeddings_dir.mkdir(parents=True)

    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CHROMA_PERSIST_DIR", str(embeddings_dir))
    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()


@pytest.fixture
def client(mock_data_dir: Path) -> TestClient:  # noqa: ARG001
    app = create_app()
    return TestClient(app)


HEADERS = {"X-API-Key": "dev-key"}


class TestHealthEndpoints:
    def test_liveness(self, client: TestClient) -> None:
        resp = client.get("/health/live")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_readiness(self, client: TestClient) -> None:
        resp = client.get("/health/ready")
        assert resp.status_code == 200


class TestAuthMiddleware:
    def test_no_api_key_returns_401(self, client: TestClient) -> None:
        resp = client.get("/api/v1/signals/AAPL")
        assert resp.status_code == 401

    def test_valid_api_key_passes(self, client: TestClient) -> None:
        resp = client.get("/api/v1/signals/AAPL", headers=HEADERS)
        assert resp.status_code == 200


class TestOptionsEndpoint:
    def test_price_option(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/options/price",
            json={
                "spot": 185.0,
                "strike": 185.0,
                "time_to_expiry": 0.0833,
                "volatility": 0.25,
            },
            headers=HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["price"] > 0
        assert "delta" in data
