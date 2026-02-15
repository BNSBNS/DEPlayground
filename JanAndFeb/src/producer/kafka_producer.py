"""Kafka producer wrapper for trade events.

This module provides a high-level interface for producing trade events to Kafka
with proper error handling, delivery callbacks, and graceful shutdown.

Includes:
- Exponential backoff retry with jitter for BufferError (Fix #8)
- Bounded retry for Kafka exceptions (Fix #2)
- Parking queue for failed messages
"""

import random
import time
from collections import deque
from typing import Callable

from confluent_kafka import KafkaException, Producer

from src.common.config import KafkaSettings, ProducerSettings, get_settings
from src.common.kafka_utils import (
    create_producer,
    DeliveryCallbackMixin,
    serialize_message,
)
from src.common.logging_config import get_logger
from src.common.models import TradeEvent
from src.producer.trade_generator import TradeGenerator
from src.producer import metrics

logger = get_logger(__name__)


class TradeProducer(DeliveryCallbackMixin):
    """High-level trade event producer.

    Produces trade events to Kafka with:
    - Configurable production rate
    - Burst mode support for simulating market volatility
    - Graceful shutdown with message flushing
    - Delivery confirmation via callbacks (via DeliveryCallbackMixin)
    """

    def __init__(
        self,
        kafka_settings: KafkaSettings | None = None,
        producer_settings: ProducerSettings | None = None,
        *,
        generator: TradeGenerator | None = None,
    ) -> None:
        """Initialize the trade producer.

        Args:
            kafka_settings: Kafka configuration.
            producer_settings: Producer-specific configuration.
            generator: Trade generator instance. If None, creates a new one.
        """
        settings = get_settings()
        self.kafka_settings = kafka_settings or settings.kafka
        self.producer_settings = producer_settings or settings.producer

        self.generator = generator or TradeGenerator()
        self._producer: Producer | None = None
        self._running = False

        # Statistics
        self._total_produced = 0

        # Parking queue for failed messages (Fix #2)
        self._parking_queue: deque[tuple[TradeEvent, str]] = deque(
            maxlen=self.producer_settings.parking_queue_max_size
        )

    @property
    def producer(self) -> Producer:
        """Get or create the Kafka producer."""
        if self._producer is None:
            self._producer = create_producer(self.kafka_settings)
        return self._producer

    def _on_delivery_failure(self, err: Exception, _msg: object) -> None:
        """Handle delivery failure - update metrics and log."""
        metrics.trades_failed.inc()
        logger.error(
            "Trade delivery failed",
            error=str(err),
            total_failed=self._delivery_errors,
        )

    def _on_delivery_success(self, _msg: object) -> None:
        """Handle successful delivery."""
        logger.debug("Trade delivered successfully")

    def produce_trade(self, trade: TradeEvent) -> None:
        """Produce a single trade event with retry logic.

        Separate retry strategies:
        - BufferError: Max 5 retries with exponential backoff (Fix #8)
        - KafkaException: Max 3 retries with exponential backoff (Fix #2)
        - Failed messages go to parking queue

        Args:
            trade: The trade event to produce.
        """
        start_time = time.perf_counter()
        key = trade.to_kafka_key()
        value = serialize_message(trade.to_kafka_value())

        for attempt in range(self.producer_settings.buffer_retry_max):
            try:
                self.producer.produce(
                    topic=self.kafka_settings.topic,
                    key=key,
                    value=value,
                    callback=self._delivery_callback,
                )
                self._total_produced += 1
                metrics.trades_produced.labels(symbol=trade.symbol).inc()
                self.producer.poll(0)

                if attempt > 0:
                    metrics.producer_buffer_full_retries_total.labels(status="success").inc()

                metrics.produce_duration.observe(time.perf_counter() - start_time)
                return

            except BufferError:
                if attempt == self.producer_settings.buffer_retry_max - 1:
                    self._parking_queue.append((trade, "BufferError"))
                    metrics.parking_queue_size.set(len(self._parking_queue))
                    metrics.producer_buffer_full_retries_total.labels(status="failure").inc()
                    logger.error("Buffer full after retries, parked", symbol=trade.symbol)
                    break

                backoff = min(2 ** attempt, self.producer_settings.buffer_retry_backoff_max)
                jitter = backoff * random.random() * self.producer_settings.buffer_retry_jitter
                self.producer.poll(backoff + jitter)

            except KafkaException as e:
                # Use same retry ceiling as the loop bound for consistency
                if attempt >= self.producer_settings.buffer_retry_max - 1:
                    self._parking_queue.append((trade, str(e)))
                    metrics.parking_queue_size.set(len(self._parking_queue))
                    metrics.kafka_produce_retries_total.labels(status="failure").inc()
                    logger.error("Kafka error after retries, parked", symbol=trade.symbol, error=str(e))
                    break

                backoff = min(2 ** attempt, self.producer_settings.buffer_retry_backoff_max)
                jitter = backoff * random.random() * self.producer_settings.buffer_retry_jitter
                time.sleep(backoff + jitter)
                if attempt > 0:
                    metrics.kafka_produce_retries_total.labels(status="success").inc()

        metrics.produce_duration.observe(time.perf_counter() - start_time)

    def run(
        self,
        *,
        duration_seconds: int | None = None,
        on_trade: Callable[[TradeEvent], None] | None = None,
    ) -> None:
        """Run the producer continuously.

        Produces trades at the configured rate, with periodic burst patterns
        if burst mode is enabled.

        Args:
            duration_seconds: Total duration to run. If None, runs indefinitely.
            on_trade: Optional callback invoked for each trade (for monitoring).
        """
        self._running = True
        start_time = time.time()
        last_burst_time = start_time
        in_burst = False
        burst_end_time = 0.0

        rate = self.producer_settings.rate
        burst_rate = rate * self.producer_settings.burst_multiplier

        logger.info(
            "Starting trade producer",
            rate=rate,
            burst_enabled=self.producer_settings.burst_enabled,
            topic=self.kafka_settings.topic,
        )

        try:
            while self._running:
                current_time = time.time()

                # Check duration limit
                if duration_seconds and (current_time - start_time) >= duration_seconds:
                    logger.info("Duration limit reached, stopping")
                    break

                # Handle burst mode transitions
                if self.producer_settings.burst_enabled:
                    if not in_burst:
                        # Check if it's time to start a burst
                        if (
                            current_time - last_burst_time
                            >= self.producer_settings.burst_interval
                        ):
                            in_burst = True
                            burst_end_time = (
                                current_time + self.producer_settings.burst_duration
                            )
                            logger.info(
                                "Starting burst mode",
                                burst_rate=burst_rate,
                                duration=self.producer_settings.burst_duration,
                            )
                    else:
                        # Check if burst should end
                        if current_time >= burst_end_time:
                            in_burst = False
                            last_burst_time = current_time
                            logger.info("Ending burst mode", normal_rate=rate)

                # Determine current rate and generate trade
                current_rate = burst_rate if in_burst else rate
                trade = self.generator.generate_trade(is_burst=in_burst)

                # Update metrics
                metrics.current_rate.set(current_rate)
                metrics.burst_mode_active.set(1 if in_burst else 0)

                # Produce the trade
                self.produce_trade(trade)

                # Invoke callback if provided
                if on_trade:
                    on_trade(trade)

                # Log progress periodically
                if self._total_produced % 1000 == 0:
                    logger.info(
                        "Production progress",
                        total_produced=self._total_produced,
                        failed=self._delivery_errors,
                        in_burst=in_burst,
                    )

                # Sleep to maintain rate
                sleep_time = 1.0 / current_rate
                time.sleep(sleep_time)

        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        finally:
            self.stop()

    def _drain_parking_queue(self) -> None:
        """Attempt to re-produce messages waiting in the parking queue.

        Called during shutdown so buffered trades are not silently dropped.
        """
        if not self._parking_queue:
            return

        count = len(self._parking_queue)
        logger.info("Draining parking queue", count=count)
        drained = 0

        while self._parking_queue:
            trade, _ = self._parking_queue.popleft()
            try:
                key = trade.to_kafka_key()
                value = serialize_message(trade.to_kafka_value())
                self.producer.produce(
                    topic=self.kafka_settings.topic,
                    key=key,
                    value=value,
                    callback=self._delivery_callback,
                )
                drained += 1
            except Exception as e:
                logger.warning(
                    "Parking queue drain failed for message",
                    symbol=trade.symbol,
                    error=str(e),
                )
                # Stop draining if the producer itself is unhealthy
                break

        metrics.parking_queue_size.set(len(self._parking_queue))
        logger.info(
            "Parking queue drain complete",
            drained=drained,
            remaining=len(self._parking_queue),
        )

    def stop(self) -> None:
        """Stop the producer and flush pending messages."""
        self._running = False

        if self._producer is not None:
            # Attempt to drain parked messages before flushing
            self._drain_parking_queue()
            logger.info("Flushing pending messages...")
            # Wait up to 10 seconds for messages to be delivered
            remaining = self._producer.flush(timeout=10.0)
            if remaining > 0:
                logger.warning(
                    "Some messages not delivered",
                    remaining=remaining,
                )

        logger.info(
            "Producer stopped",
            total_produced=self._total_produced,
            failed=self._delivery_errors,
            parking_queue_dropped=len(self._parking_queue),
        )

    def get_stats(self) -> dict[str, int]:
        """Get production statistics.

        Returns:
            Dictionary with total_produced and failed_deliveries counts.
        """
        return {
            "total_produced": self._total_produced,
            "failed_deliveries": self._delivery_errors,
        }
