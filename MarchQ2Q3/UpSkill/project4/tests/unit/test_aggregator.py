from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.processors.aggregator import (
    WINDOW_CONFIGS,
    WindowAggregator,
    _truncate_to_window,
    _window_key,
)


class TestWindowTruncation:
    """Test the tumbling window boundary truncation logic."""

    def test_truncate_1m_window(self) -> None:
        ts = datetime(2026, 2, 26, 10, 0, 45, tzinfo=timezone.utc)
        result = _truncate_to_window(ts, 60)
        assert result.minute == 0
        assert result.second == 0

    def test_truncate_5m_window(self) -> None:
        ts = datetime(2026, 2, 26, 10, 7, 30, tzinfo=timezone.utc)
        result = _truncate_to_window(ts, 300)
        assert result.minute == 5
        assert result.second == 0

    def test_truncate_1h_window(self) -> None:
        ts = datetime(2026, 2, 26, 10, 45, 0, tzinfo=timezone.utc)
        result = _truncate_to_window(ts, 3600)
        assert result.minute == 0
        assert result.second == 0

    def test_truncate_at_boundary(self) -> None:
        ts = datetime(2026, 2, 26, 10, 0, 0, tzinfo=timezone.utc)
        result = _truncate_to_window(ts, 60)
        assert result == ts

    def test_truncate_just_before_boundary(self) -> None:
        ts = datetime(2026, 2, 26, 10, 0, 59, tzinfo=timezone.utc)
        result = _truncate_to_window(ts, 60)
        expected = datetime(2026, 2, 26, 10, 0, 0, tzinfo=timezone.utc)
        assert result == expected


class TestWindowKey:
    def test_key_format(self) -> None:
        ws = datetime(2026, 2, 26, 10, 0, 0, tzinfo=timezone.utc)
        key = _window_key("sales:orders", "us-east", "1m", ws)
        assert key == "win:sales:orders:us-east:1m:20260226T100000"

    def test_key_different_dimensions(self) -> None:
        ws = datetime(2026, 2, 26, 10, 5, 0, tzinfo=timezone.utc)
        k1 = _window_key("metric", "dim-a", "5m", ws)
        k2 = _window_key("metric", "dim-b", "5m", ws)
        assert k1 != k2


class TestWindowConfigs:
    def test_all_windows_configured(self) -> None:
        assert "1m" in WINDOW_CONFIGS
        assert "5m" in WINDOW_CONFIGS
        assert "1h" in WINDOW_CONFIGS

    def test_window_durations(self) -> None:
        assert WINDOW_CONFIGS["1m"][0] == 60
        assert WINDOW_CONFIGS["5m"][0] == 300
        assert WINDOW_CONFIGS["1h"][0] == 3600

    def test_ttl_multiplier(self) -> None:
        for _, (duration, ttl_mult) in WINDOW_CONFIGS.items():
            assert ttl_mult >= 2, "TTL multiplier should be at least 2x"


class TestWindowAggregator:
    @pytest.fixture
    def aggregator(self, mock_redis: AsyncMock) -> WindowAggregator:
        return WindowAggregator(mock_redis)

    async def test_add_to_windows_integer(
        self, aggregator: WindowAggregator, mock_redis: AsyncMock
    ) -> None:
        ts = "2026-02-26T10:00:30+00:00"
        await aggregator.add_to_windows("test_metric", "dim", ts, value=5.0)

        pipe = mock_redis.pipeline.return_value
        pipe.execute.assert_called_once()

    async def test_add_to_windows_float(
        self, aggregator: WindowAggregator, mock_redis: AsyncMock
    ) -> None:
        ts = "2026-02-26T10:00:30+00:00"
        await aggregator.add_to_windows(
            "test_metric", "dim", ts, value=99.95, integer=False
        )

        pipe = mock_redis.pipeline.return_value
        pipe.execute.assert_called_once()

    async def test_get_window_empty(
        self, aggregator: WindowAggregator, mock_redis: AsyncMock
    ) -> None:
        mock_redis.hgetall.return_value = {}
        result = await aggregator.get_window(
            "metric", "dim", "1m", "2026-02-26T10:00:00+00:00"
        )
        assert result == {}

    async def test_get_window_with_data(
        self, aggregator: WindowAggregator, mock_redis: AsyncMock
    ) -> None:
        mock_redis.hgetall.return_value = {
            b"count": b"42",
            b"window_start": b"2026-02-26T10:00:00+00:00",
            b"window_end": b"2026-02-26T10:01:00+00:00",
        }
        result = await aggregator.get_window(
            "metric", "dim", "1m", "2026-02-26T10:00:30+00:00"
        )
        assert result["count"] == "42"
        assert "window_start" in result
