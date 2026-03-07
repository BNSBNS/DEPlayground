from __future__ import annotations

from datetime import datetime, timedelta, timezone

import redis.asyncio as aioredis

from src.logging import get_logger

log = get_logger(__name__)

# Window durations in seconds and their TTL multiplier
WINDOWS: dict[str, int] = {
    "1m": 60,
    "5m": 300,
    "1h": 3600,
}


def _window_start(ts: datetime, window_seconds: int) -> str:
    """Truncate timestamp to window boundary and return as string."""
    epoch = ts.replace(tzinfo=timezone.utc).timestamp()
    start = int(epoch // window_seconds) * window_seconds
    return datetime.fromtimestamp(start, tz=timezone.utc).strftime("%Y%m%dT%H%M%S")


class RedisAggregator:
    """Atomic counter-based aggregation using Redis HINCRBY/HINCRBYFLOAT.

    Key format: agg:{metric}:{window_name}:{dimension}:{window_start}
    TTL = 2x window duration.
    """

    def __init__(self, redis: aioredis.Redis) -> None:
        self._redis = redis

    def _build_keys(
        self, metric: str, dimension: str, timestamp: str
    ) -> list[tuple[str, int]]:
        """Build Redis keys for all window sizes. Returns (key, ttl) pairs."""
        ts = datetime.fromisoformat(timestamp)
        keys: list[tuple[str, int]] = []
        for window_name, duration in WINDOWS.items():
            ws = _window_start(ts, duration)
            key = f"agg:{metric}:{window_name}:{dimension}:{ws}"
            ttl = duration * 2
            keys.append((key, ttl))
        return keys

    async def increment(
        self, metric: str, dimension: str, timestamp: str, amount: int = 1
    ) -> None:
        """Atomically increment an integer counter across all windows."""
        pipe = self._redis.pipeline()
        for key, ttl in self._build_keys(metric, dimension, timestamp):
            pipe.hincrby(key, "count", amount)
            pipe.expire(key, ttl)
        await pipe.execute()

    async def increment_float(
        self, metric: str, dimension: str, timestamp: str, amount: float
    ) -> None:
        """Atomically increment a float sum across all windows."""
        pipe = self._redis.pipeline()
        for key, ttl in self._build_keys(metric, dimension, timestamp):
            pipe.hincrbyfloat(key, "sum", amount)
            pipe.hincrby(key, "count", 1)
            pipe.expire(key, ttl)
        await pipe.execute()

    async def get_current(
        self, metric: str, dimension: str, window_name: str
    ) -> dict[str, str]:
        """Get the current window's aggregation data."""
        now = datetime.now(tz=timezone.utc)
        duration = WINDOWS[window_name]
        ws = _window_start(now, duration)
        key = f"agg:{metric}:{window_name}:{dimension}:{ws}"

        data = await self._redis.hgetall(key)
        return {
            (k.decode() if isinstance(k, bytes) else k): (
                v.decode() if isinstance(v, bytes) else v
            )
            for k, v in data.items()
        }

    async def scan_completed(
        self, metric: str, window_name: str
    ) -> list[tuple[str, dict[str, str]]]:
        """Find completed window keys (window_end has passed)."""
        now = datetime.now(tz=timezone.utc)
        duration = WINDOWS[window_name]
        current_ws = _window_start(now, duration)
        pattern = f"agg:{metric}:{window_name}:*"

        results: list[tuple[str, dict[str, str]]] = []
        async for key in self._redis.scan_iter(match=pattern, count=100):
            key_str = key.decode() if isinstance(key, bytes) else key
            # The window start is the last segment of the key
            key_ws = key_str.rsplit(":", 1)[-1]
            if key_ws < current_ws:
                data = await self._redis.hgetall(key)
                decoded = {
                    (k.decode() if isinstance(k, bytes) else k): (
                        v.decode() if isinstance(v, bytes) else v
                    )
                    for k, v in data.items()
                }
                results.append((key_str, decoded))
        return results
