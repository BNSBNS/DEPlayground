"""Tests for fraud scoring API (Phase 6).

Uses httpx TestClient with a lightweight mock model.
"""

from __future__ import annotations

import numpy as np
import pytest
from httpx import ASGITransport, AsyncClient

from src.api.main import app, set_model, state
from src.features.pipeline import FEATURE_COLUMNS
from src.models.base import BaseDetector, Explanation


class _MockDetector(BaseDetector):
    """Deterministic mock detector for API testing."""

    def fit(self, X: np.ndarray, y: np.ndarray | None = None) -> None:
        pass

    def predict(self, X: np.ndarray) -> np.ndarray:
        result: np.ndarray = np.ones(X.shape[0], dtype=int)
        return result

    def score(self, X: np.ndarray) -> np.ndarray:
        result: np.ndarray = np.full(X.shape[0], 0.85)
        return result

    def explain(self, X: np.ndarray, feature_names: list[str]) -> list[Explanation]:
        return [
            [(feature_names[0], 0.5), (feature_names[1], 0.3), (feature_names[2], 0.2)]
            for _ in range(X.shape[0])
        ]


@pytest.fixture(autouse=True)
def _reset_state() -> None:
    """Reset API state before each test."""
    set_model(_MockDetector(), "mock", "MockDetector")
    state.total_scored = 0
    state.total_flagged = 0
    state.score_sum = 0.0


def _make_features() -> dict[str, float]:
    """Generate a valid feature dict."""
    return dict.fromkeys(FEATURE_COLUMNS, 0.5)


@pytest.fixture()
async def client() -> AsyncClient:
    """Async test client."""
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


class TestScoreEndpoint:
    """POST /api/v1/score tests."""

    async def test_returns_200(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/score",
            json={"transaction_id": "tx-1", "user_id": "u1", "features": _make_features()},
        )
        assert resp.status_code == 200

    async def test_response_shape(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/score",
            json={"transaction_id": "tx-1", "user_id": "u1", "features": _make_features()},
        )
        data = resp.json()
        assert data["transaction_id"] == "tx-1"
        assert 0 <= data["fraud_score"] <= 1
        assert isinstance(data["is_fraud"], bool)
        assert len(data["explanation"]) == 3

    async def test_explanation_format(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/score",
            json={"transaction_id": "tx-1", "user_id": "u1", "features": _make_features()},
        )
        for item in resp.json()["explanation"]:
            assert "feature" in item
            assert "contribution" in item


class TestBatchEndpoint:
    """POST /api/v1/batch tests."""

    async def test_returns_200(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/batch",
            json={
                "transactions": [
                    {"transaction_id": "tx-1", "user_id": "u1", "features": _make_features()},
                    {"transaction_id": "tx-2", "user_id": "u2", "features": _make_features()},
                ]
            },
        )
        assert resp.status_code == 200

    async def test_batch_counts(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/batch",
            json={
                "transactions": [
                    {"transaction_id": f"tx-{i}", "user_id": f"u{i}", "features": _make_features()}
                    for i in range(5)
                ]
            },
        )
        data = resp.json()
        assert data["total"] == 5
        assert data["flagged"] == 5  # mock always predicts fraud


class TestModelInfoEndpoint:
    """GET /api/v1/model-info tests."""

    async def test_returns_model_info(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/model-info")
        assert resp.status_code == 200
        data = resp.json()
        assert data["model_name"] == "mock"
        assert data["feature_count"] == len(FEATURE_COLUMNS)
        assert len(data["feature_names"]) == len(FEATURE_COLUMNS)


class TestStatsEndpoint:
    """GET /api/v1/stats tests."""

    async def test_initial_stats_zero(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/stats")
        data = resp.json()
        assert data["total_scored"] == 0
        assert data["total_flagged"] == 0

    async def test_stats_update_after_scoring(self, client: AsyncClient) -> None:
        await client.post(
            "/api/v1/score",
            json={"transaction_id": "tx-1", "user_id": "u1", "features": _make_features()},
        )
        resp = await client.get("/api/v1/stats")
        data = resp.json()
        assert data["total_scored"] == 1
        assert data["total_flagged"] == 1


class TestHealth:
    """GET /health tests."""

    async def test_health_ok(self, client: AsyncClient) -> None:
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        assert resp.json()["model_loaded"] is True
