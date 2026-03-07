"""Main entry point: runs all consumer tasks with graceful shutdown."""
from __future__ import annotations

import asyncio
import signal

import redis.asyncio as aioredis

from src.aggregation.flusher import AggregationFlusher
from src.aggregation.redis_agg import RedisAggregator
from src.config import settings
from src.consumers.anomaly import AnomalyConsumer
from src.consumers.clickstream import ClickstreamConsumer
from src.consumers.orders import OrderConsumer
from src.consumers.payments import PaymentConsumer
from src.db.pool import close_pool, get_pool, init_db
from src.logging import get_logger, setup_logging

log = get_logger(__name__)


async def main() -> None:
    setup_logging()
    log.info("worker_starting")

    from src.metrics import start_metrics_server  # noqa: PLC0415
    start_metrics_server(port=9100)
    log.info("prometheus_metrics_server_started", port=9100)

    # Initialize dependencies
    redis = aioredis.from_url(settings.redis.url, decode_responses=False)
    await init_db()
    pool = await get_pool()
    aggregator = RedisAggregator(redis)

    shutdown_event = asyncio.Event()

    # Set up signal handlers for graceful shutdown
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, shutdown_event.set)

    # Create consumer instances
    order_consumer = OrderConsumer(redis, aggregator)
    click_consumer = ClickstreamConsumer(redis, aggregator)
    payment_consumer = PaymentConsumer(redis, aggregator)
    anomaly_consumer = AnomalyConsumer(redis)
    flusher = AggregationFlusher(redis, pool, aggregator)

    group = settings.kafka.consumer_group

    # Launch all tasks
    tasks = [
        asyncio.create_task(order_consumer.run(group, shutdown_event)),
        asyncio.create_task(click_consumer.run(group, shutdown_event)),
        asyncio.create_task(payment_consumer.run(group, shutdown_event)),
        asyncio.create_task(anomaly_consumer.run(shutdown_event)),
        asyncio.create_task(flusher.run(60, shutdown_event)),
    ]

    log.info("worker_started", tasks=len(tasks))

    try:
        await asyncio.gather(*tasks)
    except Exception:
        log.exception("worker_error")
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await redis.aclose()
        await close_pool()
        log.info("worker_stopped")


if __name__ == "__main__":
    asyncio.run(main())
