"""Performance and edge case tests (Phase 8).

Tests API latency, concurrent requests, and malformed input handling.
"""

from __future__ import annotations

import time

import numpy as np
import pytest
from httpx import ASGITransport, AsyncClient

from src.api.main import app, set_model, state
from src.features.pipeline import FEATURE_COLUMNS
from src.models.base import BaseDetector, Explanation


class _FastMockDetector(BaseDetector):
    """Minimal mock for performance testing."""

    def fit(self, X: np.ndarray, y: np.ndarray | None = None) -> None:
        pass

    def predict(self, X: np.ndarray) -> np.ndarray:
        result: np.ndarray = np.zeros(X.shape[0], dtype=int)
        return result

    def score(self, X: np.ndarray) -> np.ndarray:
        result: np.ndarray = np.full(X.shape[0], 0.3)
        return result

    def explain(self, X: np.ndarray, feature_names: list[str]) -> list[Explanation]:
        return [
            [(feature_names[0], 0.1), (feature_names[1], 0.05), (feature_names[2], 0.02)]
            for _ in range(X.shape[0])
        ]


@pytest.fixture(autouse=True)
def _reset_state() -> None:
    """Reset API state before each test."""
    set_model(_FastMockDetector(), "perf-mock", "MockDetector")
    state.total_scored = 0
    state.total_flagged = 0
    state.score_sum = 0.0


def _make_features() -> dict[str, float]:
    return dict.fromkeys(FEATURE_COLUMNS, 0.5)


@pytest.fixture()
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


class TestScoringLatency:
    """Single request latency tests."""

    async def test_single_score_under_200ms(self, client: AsyncClient) -> None:
        """Single scoring request must complete in <200ms."""
        payload = {"transaction_id": "tx-1", "user_id": "u1", "features": _make_features()}
        start = time.perf_counter()
        resp = await client.post("/api/v1/score", json=payload)
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert resp.status_code == 200
        assert elapsed_ms < 200, f"Scoring took {elapsed_ms:.1f}ms, expected <200ms"


class TestBatchPerformance:
    """Batch endpoint performance tests."""

    async def test_batch_100_under_2s(self, client: AsyncClient) -> None:
        """Batch of 100 transactions should complete in <2s."""
        txs = [
            {"transaction_id": f"tx-{i}", "user_id": f"u{i}", "features": _make_features()}
            for i in range(100)
        ]
        start = time.perf_counter()
        resp = await client.post("/api/v1/batch", json={"transactions": txs})
        elapsed_s = time.perf_counter() - start
        assert resp.status_code == 200
        assert elapsed_s < 2.0, f"Batch took {elapsed_s:.2f}s, expected <2s"
        assert resp.json()["total"] == 100


class TestMalformedInput:
    """Edge case and malformed input tests."""

    async def test_missing_features(self, client: AsyncClient) -> None:
        """Request with empty features dict should still work."""
        resp = await client.post(
            "/api/v1/score",
            json={"transaction_id": "tx-1", "user_id": "u1", "features": {}},
        )
        assert resp.status_code == 200

    async def test_extra_features_ignored(self, client: AsyncClient) -> None:
        """Extra features should be silently ignored."""
        features = _make_features()
        features["nonexistent_feature"] = 999.0
        resp = await client.post(
            "/api/v1/score",
            json={"transaction_id": "tx-1", "user_id": "u1", "features": features},
        )
        assert resp.status_code == 200

    async def test_negative_amounts(self, client: AsyncClient) -> None:
        """Negative feature values should not crash."""
        features = _make_features()
        features["amount_log"] = -100.0
        resp = await client.post(
            "/api/v1/score",
            json={"transaction_id": "tx-1", "user_id": "u1", "features": features},
        )
        assert resp.status_code == 200

    async def test_extreme_values(self, client: AsyncClient) -> None:
        """Extreme feature values should not crash."""
        features = dict.fromkeys(FEATURE_COLUMNS, 1e10)
        resp = await client.post(
            "/api/v1/score",
            json={"transaction_id": "tx-1", "user_id": "u1", "features": features},
        )
        assert resp.status_code == 200

    async def test_missing_required_field(self, client: AsyncClient) -> None:
        """Missing required field should return 422."""
        resp = await client.post(
            "/api/v1/score",
            json={"transaction_id": "tx-1"},  # missing user_id and features
        )
        assert resp.status_code == 422

    async def test_invalid_json(self, client: AsyncClient) -> None:
        """Invalid JSON should return 422."""
        resp = await client.post(
            "/api/v1/score",
            content=b"not json",
            headers={"content-type": "application/json"},
        )
        assert resp.status_code == 422

    async def test_empty_batch(self, client: AsyncClient) -> None:
        """Empty batch should return valid response with 0 results."""
        resp = await client.post("/api/v1/batch", json={"transactions": []})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0
