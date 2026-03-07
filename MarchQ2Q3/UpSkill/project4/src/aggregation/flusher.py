from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone

import asyncpg
import redis.asyncio as aioredis

from src.aggregation.redis_agg import WINDOWS, RedisAggregator
from src.logging import get_logger

log = get_logger(__name__)


def _decode_value(data: dict, key_bytes: bytes, key_str: str, default: str = "0") -> str:
    """Decode a value from a Redis hash that may have bytes or str keys."""
    raw = data.get(key_bytes) or data.get(key_str)
    if raw is None:
        return default
    return raw.decode() if isinstance(raw, bytes) else str(raw)


class AggregationFlusher:
    """Periodically flushes completed Redis windows to Postgres serving tables."""

    def __init__(
        self, redis: aioredis.Redis, pool: asyncpg.Pool, aggregator: RedisAggregator
    ) -> None:
        self._redis = redis
        self._pool = pool
        self._aggregator = aggregator

    async def flush_sales(self) -> int:
        """Flush completed sales windows to real_time_sales table."""
        flushed = 0
        for window_name in WINDOWS:
            completed = await self._aggregator.scan_completed(
                "sales:orders", window_name
            )
            for key, data in completed:
                # Key format: agg:sales:orders:{window}:{dimension}:{window_start}
                parts = key.split(":")
                if len(parts) < 6:
                    continue
                dimension = parts[4]
                ws_str = parts[5]
                duration = WINDOWS[window_name]

                window_start = datetime.strptime(ws_str, "%Y%m%dT%H%M%S").replace(
                    tzinfo=timezone.utc
                )
                window_end = window_start + timedelta(seconds=duration)

                # Get companion revenue data
                rev_key = key.replace("sales:orders", "sales:revenue")
                rev_data = await self._redis.hgetall(rev_key)
                revenue = float(_decode_value(rev_data, b"sum", "sum"))
                count = int(data.get("count", "0"))
                avg_value = revenue / count if count > 0 else 0.0

                async with self._pool.acquire() as conn:
                    await conn.execute(
                        """
                        INSERT INTO real_time_sales
                            (window_start, window_end, region, total_orders,
                             total_revenue, avg_order_value, updated_at)
                        VALUES ($1, $2, $3, $4, $5, $6, NOW())
                        ON CONFLICT (window_start, window_end, region)
                        DO UPDATE SET
                            total_orders = EXCLUDED.total_orders,
                            total_revenue = EXCLUDED.total_revenue,
                            avg_order_value = EXCLUDED.avg_order_value,
                            updated_at = NOW()
                        """,
                        window_start,
                        window_end,
                        dimension,
                        count,
                        revenue,
                        avg_value,
                    )

                await self._redis.delete(key)
                if rev_key != key:
                    await self._redis.delete(rev_key)
                flushed += 1

        return flushed

    async def flush_anomalies(self) -> int:
        """Flush anomaly flags to Postgres."""
        flushed = 0
        members = await self._redis.zrange("anomalies:timeline", 0, -1)

        for anomaly_id_raw in members:
            anomaly_id = (
                anomaly_id_raw.decode()
                if isinstance(anomaly_id_raw, bytes)
                else anomaly_id_raw
            )
            raw = await self._redis.get(f"anomaly:{anomaly_id}")
            if raw is None:
                continue

            data = json.loads(raw.decode() if isinstance(raw, bytes) else raw)

            async with self._pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO anomaly_flags
                        (anomaly_id, rule_name, severity, entity_type, entity_id,
                         metric_name, metric_value, threshold, description, detected_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    ON CONFLICT (anomaly_id) DO NOTHING
                    """,
                    data["anomaly_id"],
                    data["rule_name"],
                    data["severity"],
                    data["entity_type"],
                    data["entity_id"],
                    data["metric_name"],
                    data["metric_value"],
                    data["threshold"],
                    data["description"],
                    datetime.fromisoformat(data["detected_at"]),
                )

            await self._redis.delete(f"anomaly:{anomaly_id}")
            await self._redis.zrem("anomalies:timeline", anomaly_id)
            flushed += 1

        return flushed

    async def run(
        self, interval: int = 60, shutdown_event: asyncio.Event | None = None
    ) -> None:
        """Periodically flush completed windows to Postgres."""
        log.info("flusher_started", interval=interval)
        try:
            while True:
                if shutdown_event and shutdown_event.is_set():
                    break
                try:
                    sales_count = await self.flush_sales()
                    anomaly_count = await self.flush_anomalies()
                    if sales_count or anomaly_count:
                        log.info(
                            "flush_completed",
                            sales=sales_count,
                            anomalies=anomaly_count,
                        )
                except Exception:
                    log.exception("flush_error")
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            log.info("flusher_cancelled")
