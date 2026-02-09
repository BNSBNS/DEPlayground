"""Kafka streamer service for WebSocket broadcasting.

Consumes from Kafka trades topic and broadcasts to connected WebSocket clients.
"""

import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Any

from confluent_kafka import Consumer, KafkaError

from src.common.config import KafkaSettings
from src.common.logging_config import get_logger
from src.common.models import TradeEvent
from src.consumer.windowed_aggregator import WindowedAggregator

logger = get_logger(__name__)


class KafkaStreamer:
    """Kafka consumer that broadcasts messages to WebSocket clients.

    Manages subscriptions from WebSocket handlers and distributes
    messages from Kafka to all connected clients.
    """

    def __init__(self, settings: KafkaSettings) -> None:
        """Initialize the Kafka streamer.

        Args:
            settings: Kafka connection settings.
        """
        self._settings = settings
        self._running = False
        self._connected = False

        # Subscriber registries
        # client_id -> (queue, symbol_filter or None)
        self._trade_subscribers: dict[int, tuple[asyncio.Queue[dict[str, Any]], str | None]] = {}
        self._aggregate_subscribers: dict[int, asyncio.Queue[dict[str, Any]]] = {}

        # Windowed aggregator for computing real-time aggregates
        self._aggregator = WindowedAggregator(window_duration_seconds=60)
        self._last_idle_flush: float = 0.0

        # Consumer instance (created on start)
        self._consumer: Consumer | None = None

    def is_connected(self) -> bool:
        """Check if Kafka connection is active."""
        return self._connected

    async def subscribe(
        self,
        client_id: int,
        queue: asyncio.Queue[dict[str, Any]],
        symbol_filter: str | None = None,
    ) -> None:
        """Subscribe a WebSocket client to trade events.

        Args:
            client_id: Unique identifier for the client.
            queue: Async queue to push messages to.
            symbol_filter: Optional symbol to filter trades.
        """
        self._trade_subscribers[client_id] = (queue, symbol_filter)
        logger.debug(
            "Client subscribed to trades",
            client_id=client_id,
            symbol_filter=symbol_filter,
            total_subscribers=len(self._trade_subscribers),
        )

    async def unsubscribe(self, client_id: int) -> None:
        """Unsubscribe a client from trade events."""
        self._trade_subscribers.pop(client_id, None)
        logger.debug(
            "Client unsubscribed from trades",
            client_id=client_id,
            total_subscribers=len(self._trade_subscribers),
        )

    async def subscribe_aggregates(
        self,
        client_id: int,
        queue: asyncio.Queue[dict[str, Any]],
    ) -> None:
        """Subscribe a client to completed aggregates."""
        self._aggregate_subscribers[client_id] = queue
        logger.debug(
            "Client subscribed to aggregates",
            client_id=client_id,
            total_subscribers=len(self._aggregate_subscribers),
        )

    async def unsubscribe_aggregates(self, client_id: int) -> None:
        """Unsubscribe a client from aggregates."""
        self._aggregate_subscribers.pop(client_id, None)
        logger.debug(
            "Client unsubscribed from aggregates",
            client_id=client_id,
            total_subscribers=len(self._aggregate_subscribers),
        )

    async def start(self) -> None:
        """Start consuming from Kafka and broadcasting to subscribers."""
        self._running = True

        # Create consumer with a unique group for the API
        # (separate from the main consumer that writes to DB)
        config = {
            "bootstrap.servers": self._settings.bootstrap_servers,
            "group.id": f"{self._settings.consumer_group}-api-streamer",
            "auto.offset.reset": "latest",  # Only stream new messages
            "enable.auto.commit": True,
            "auto.commit.interval.ms": 5000,
            "fetch.min.bytes": 1,
            "fetch.max.wait.ms": 100,  # Low latency
            "client.id": "trade-api-streamer",
        }

        self._consumer = Consumer(config)
        self._consumer.subscribe([self._settings.topic])
        self._connected = True

        logger.info(
            "Kafka streamer started",
            topic=self._settings.topic,
            bootstrap_servers=self._settings.bootstrap_servers,
        )

        try:
            while self._running:
                # Offload the blocking poll to a thread so the event loop
                # stays free. 100 ms timeout gives a natural cadence without
                # busy-waiting.
                msg = await asyncio.to_thread(self._consumer.poll, 0.1)

                # Periodic idle flush: emit windows that closed while traffic
                # was quiet (wall-clock based, same pattern as the consumer).
                now = time.monotonic()
                if now - self._last_idle_flush >= 5.0:
                    await self._flush_stale_aggregates()
                    self._last_idle_flush = now

                if msg is None:
                    continue

                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    logger.error("Kafka error", error=str(msg.error()))
                    continue

                # Parse message
                try:
                    data = json.loads(msg.value().decode("utf-8"))

                    # Add metadata
                    data["_partition"] = msg.partition()
                    data["_offset"] = msg.offset()
                    data["_timestamp"] = datetime.now(timezone.utc).isoformat()

                    # Broadcast to trade subscribers
                    await self._broadcast_trade(data)

                    # Process through aggregator and broadcast completed windows
                    await self._process_for_aggregates(data)

                except json.JSONDecodeError as e:
                    logger.warning("Invalid JSON in message", error=str(e))
                except Exception as e:
                    logger.error("Error processing message", error=str(e))

        except Exception as e:
            logger.error("Kafka streamer error", error=str(e))
        finally:
            self._connected = False
            # Final flush so in-progress windows reach subscribers on shutdown
            await self._flush_all_aggregates()
            if self._consumer:
                self._consumer.close()

    async def stop(self) -> None:
        """Stop the Kafka consumer."""
        self._running = False
        logger.info("Kafka streamer stopping")

    async def _flush_stale_aggregates(self) -> None:
        """Flush windows that closed while traffic was quiet."""
        results = self._aggregator.flush_stale_windows(
            reference_time=datetime.now(timezone.utc),
        )
        await self._broadcast_aggregate_results(results)

    async def _flush_all_aggregates(self) -> None:
        """Flush all remaining windows on shutdown."""
        results = self._aggregator.flush_all()
        await self._broadcast_aggregate_results(results)

    async def _broadcast_aggregate_results(self, results: list) -> None:
        """Broadcast a list of WindowFlushResult to aggregate subscribers."""
        for result in results:
            agg = result.aggregate
            agg_data = {
                "type": "aggregate",
                "symbol": agg.symbol,
                "window_start": agg.window_start.isoformat(),
                "window_end": agg.window_end.isoformat(),
                "vwap": str(agg.vwap),
                "total_volume": str(agg.total_volume),
                "trade_count": agg.trade_count,
                "max_price": str(agg.max_price),
                "min_price": str(agg.min_price),
            }
            for queue in self._aggregate_subscribers.values():
                try:
                    queue.put_nowait(agg_data)
                except asyncio.QueueFull:
                    pass

    async def _broadcast_trade(self, data: dict[str, Any]) -> None:
        """Broadcast a trade event to all subscribed clients."""
        symbol = data.get("symbol")

        for client_id, (queue, symbol_filter) in list(self._trade_subscribers.items()):
            # Apply symbol filter if set
            if symbol_filter and symbol != symbol_filter:
                continue

            try:
                # Non-blocking put - drop if queue is full
                queue.put_nowait(data)
            except asyncio.QueueFull:
                logger.warning(
                    "Client queue full, dropping message",
                    client_id=client_id,
                )

    async def _process_for_aggregates(self, data: dict[str, Any]) -> None:
        """Process trade through aggregator and broadcast completed windows."""
        try:
            trade = TradeEvent.from_kafka_value(data)
            completed = self._aggregator.add_trade(trade)
            await self._broadcast_aggregate_results(completed)
        except Exception as e:
            logger.debug("Could not process trade for aggregates", error=str(e))
