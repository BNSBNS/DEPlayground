from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import redis.asyncio as aioredis

from src.logging import get_logger

log = get_logger(__name__)

# Window configurations: name -> (duration_seconds, ttl_multiplier)
WINDOW_CONFIGS: dict[str, tuple[int, int]] = {
    "1m": (60, 2),
    "5m": (300, 2),
    "1h": (3600, 2),
}


def _truncate_to_window(ts: datetime, window_seconds: int) -> datetime:
    """Truncate a timestamp to the start of its tumbling window."""
    epoch = ts.replace(tzinfo=timezone.utc).timestamp()
    window_start = int(epoch // window_seconds) * window_seconds
    return datetime.fromtimestamp(window_start, tz=timezone.utc)


def _window_key(metric: str, dimension: str, window_name: str, window_start: datetime) -> str:
    """Build a Redis key for a window bucket."""
    start_str = window_start.strftime("%Y%m%dT%H%M%S")
    return f"win:{metric}:{dimension}:{window_name}:{start_str}"


class WindowAggregator:
    """Tumbling and sliding window aggregation backed by Redis."""

    def __init__(self, redis: aioredis.Redis) -> None:
        self._redis = redis

    async def add_to_windows(
        self,
        metric: str,
        dimension: str,
        timestamp: str | datetime,
        value: float = 1.0,
        *,
        integer: bool = True,
    ) -> None:
        """Add a value to all configured tumbling windows."""
        if isinstance(timestamp, str):
            ts = datetime.fromisoformat(timestamp)
        else:
            ts = timestamp

        pipe = self._redis.pipeline()

        for window_name, (duration, ttl_mult) in WINDOW_CONFIGS.items():
            window_start = _truncate_to_window(ts, duration)
            key = _window_key(metric, dimension, window_name, window_start)
            ttl = duration * ttl_mult

            if integer:
                pipe.hincrby(key, "count", int(value))
            else:
                pipe.hincrbyfloat(key, "sum", value)
                pipe.hincrby(key, "count", 1)

            pipe.hsetnx(key, "window_start", window_start.isoformat())
            pipe.hsetnx(key, "window_end", (
                window_start + timedelta(seconds=duration)
            ).isoformat())
            pipe.expire(key, ttl)

        await pipe.execute()

    async def get_window(
        self, metric: str, dimension: str, window_name: str, timestamp: str | datetime
    ) -> dict[str, Any]:
        """Get the current state of a specific window."""
        if isinstance(timestamp, str):
            ts = datetime.fromisoformat(timestamp)
        else:
            ts = timestamp

        duration = WINDOW_CONFIGS[window_name][0]
        window_start = _truncate_to_window(ts, duration)
        key = _window_key(metric, dimension, window_name, window_start)

        data = await self._redis.hgetall(key)
        if not data:
            return {}

        return {
            k.decode() if isinstance(k, bytes) else k: (
                v.decode() if isinstance(v, bytes) else v
            )
            for k, v in data.items()
        }

    async def get_completed_windows(
        self, metric: str, window_name: str, before: datetime
    ) -> list[str]:
        """Find window keys that are completed (window_end < before)."""
        pattern = f"win:{metric}:*:{window_name}:*"
        keys: list[str] = []
        async for key in self._redis.scan_iter(match=pattern, count=100):
            key_str = key.decode() if isinstance(key, bytes) else key
            data = await self._redis.hgetall(key)
            window_end_raw = data.get(b"window_end") or data.get("window_end")
            if window_end_raw:
                end_str = (
                    window_end_raw.decode()
                    if isinstance(window_end_raw, bytes)
                    else window_end_raw
                )
                window_end = datetime.fromisoformat(end_str)
                if window_end.replace(tzinfo=timezone.utc) < before.replace(
                    tzinfo=timezone.utc
                ):
                    keys.append(key_str)
        return keys
