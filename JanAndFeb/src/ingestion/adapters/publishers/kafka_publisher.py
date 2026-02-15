"""Kafka publisher adapter.

Publishes EnrichedTradeEvent to Kafka topics.
"""

import json
from typing import Any

from confluent_kafka import Producer, KafkaError, KafkaException
import structlog

from src.ingestion.ports import EventPublisherPort, PublishError
from src.ingestion.domain.models import EnrichedTradeEvent
from src.common.kafka_utils import DeliveryCallbackMixin


logger = structlog.get_logger()


class KafkaPublisher(DeliveryCallbackMixin, EventPublisherPort):
    """Kafka publisher for trade events.

    Implements the EventPublisherPort interface for publishing
    EnrichedTradeEvent to Kafka topics. Uses DeliveryCallbackMixin
    for standardized delivery callback handling.

    Example:
        ```python
        publisher = KafkaPublisher(
            bootstrap_servers="localhost:9092",
            topic="trades",
        )

        await publisher.publish(event)
        await publisher.flush()
        ```
    """

    def __init__(
        self,
        bootstrap_servers: str,
        topic: str,
        acks: str = "all",
        compression_type: str = "lz4",
        batch_size: int = 16384,
        linger_ms: int = 5,
        enable_idempotence: bool = True,
        retries: int = 2147483647,
        delivery_timeout_ms: int = 120000,
    ):
        """Initialize Kafka publisher.

        Args:
            bootstrap_servers: Kafka broker addresses
            topic: Topic to publish to
            acks: Acknowledgment level ("0", "1", "all")
            compression_type: Compression algorithm
            batch_size: Maximum batch size in bytes
            linger_ms: Time to wait for batch to fill
            enable_idempotence: Enable exactly-once semantics
            retries: Maximum retry attempts
            delivery_timeout_ms: Total delivery timeout
        """
        self._bootstrap_servers = bootstrap_servers
        self._topic = topic

        self._config = {
            "bootstrap.servers": bootstrap_servers,
            "acks": acks,
            "compression.type": compression_type,
            "batch.size": batch_size,
            "linger.ms": linger_ms,
            "enable.idempotence": enable_idempotence,
            "retries": retries,
            "delivery.timeout.ms": delivery_timeout_ms,
            "retry.backoff.ms": 100,
        }

        self._producer: Producer | None = None
        self._delivered_count = 0
        self._pending_count = 0

        self._logger = logger.bind(
            component="kafka_publisher",
            topic=topic,
        )

    def _ensure_producer(self) -> Producer:
        """Ensure producer is initialized."""
        if self._producer is None:
            self._producer = Producer(self._config)
            self._logger.info("Kafka producer initialized")
        return self._producer

    def _delivery_callback(self, err: KafkaError | None, msg: Any) -> None:
        """Handle delivery confirmation with pending count tracking."""
        self._pending_count = max(0, self._pending_count - 1)
        super()._delivery_callback(err, msg)

    def _on_delivery_failure(self, err: KafkaError, msg: Any) -> None:
        """Handle delivery failure - log with context."""
        self._logger.error(
            "Delivery failed",
            error=str(err),
            topic=msg.topic(),
            partition=msg.partition(),
        )

    def _on_delivery_success(self, msg: Any) -> None:
        """Handle successful delivery - increment counter and log."""
        self._delivered_count += 1
        self._logger.debug(
            "Delivered",
            topic=msg.topic(),
            partition=msg.partition(),
            offset=msg.offset(),
        )

    def _serialize_event(self, event: EnrichedTradeEvent) -> bytes:
        """Serialize event to JSON bytes."""
        return json.dumps(event.to_kafka_value()).encode("utf-8")

    async def publish(self, event: EnrichedTradeEvent) -> None:
        """Publish a single event to Kafka.

        Args:
            event: Event to publish

        Raises:
            PublishError: If publishing fails
        """
        producer = self._ensure_producer()

        try:
            key = event.to_kafka_key()
            value = self._serialize_event(event)

            self._pending_count += 1
            producer.produce(
                topic=self._topic,
                key=key,
                value=value,
                callback=self._delivery_callback,
            )

            # Poll to trigger callbacks (non-blocking)
            producer.poll(0)

        except BufferError:
            # Revert increment: first produce didn't queue the message
            self._pending_count -= 1
            self._logger.warning("Producer buffer full, waiting...")
            producer.poll(1.0)
            try:
                self._pending_count += 1  # Re-increment for retry attempt
                producer.produce(
                    topic=self._topic,
                    key=key,
                    value=value,
                    callback=self._delivery_callback,
                )
            except Exception as e:
                self._pending_count -= 1
                raise PublishError(f"Failed to publish event: {e}", event)

        except KafkaException as e:
            self._pending_count -= 1
            raise PublishError(f"Kafka error: {e}", event)

    async def publish_batch(self, events: list[EnrichedTradeEvent]) -> None:
        """Publish multiple events to Kafka.

        Args:
            events: List of events to publish

        Raises:
            PublishError: If any publishing fails
        """
        producer = self._ensure_producer()
        errors = []

        for event in events:
            try:
                key = event.to_kafka_key()
                value = self._serialize_event(event)

                self._pending_count += 1
                producer.produce(
                    topic=self._topic,
                    key=key,
                    value=value,
                    callback=self._delivery_callback,
                )

            except BufferError:
                # Revert increment: first produce didn't queue the message
                self._pending_count -= 1
                producer.flush(timeout=10.0)
                try:
                    self._pending_count += 1  # Re-increment for retry attempt
                    producer.produce(
                        topic=self._topic,
                        key=key,
                        value=value,
                        callback=self._delivery_callback,
                    )
                except Exception as e:
                    self._pending_count -= 1
                    errors.append(str(e))

            except Exception as e:
                self._pending_count -= 1
                errors.append(str(e))

        # Poll to trigger callbacks
        producer.poll(0)

        if errors:
            raise PublishError(f"Failed to publish {len(errors)} events: {errors[0]}")

    async def flush(self) -> None:
        """Flush all pending messages.

        Blocks until all messages are delivered or timeout.
        """
        if self._producer:
            remaining = self._producer.flush(timeout=30.0)
            if remaining > 0:
                self._logger.warning(
                    "Some messages not delivered",
                    remaining=remaining,
                )

    async def health_check(self) -> bool:
        """Check if publisher is healthy."""
        if self._producer is None:
            return False

        # Check if we can poll without errors
        try:
            self._producer.poll(0)
            return True
        except Exception:
            return False

    def close(self) -> None:
        """Close the producer."""
        if self._producer:
            remaining = self._producer.flush(timeout=10.0)
            if remaining > 0:
                self._logger.warning(
                    "Closing with pending messages",
                    remaining=remaining,
                )
            self._producer = None
            self._logger.info(
                "Kafka producer closed",
                delivered=self._delivered_count,
                failed=self._delivery_errors,
            )

    def get_stats(self) -> dict[str, Any]:
        """Get publisher statistics."""
        return {
            "bootstrap_servers": self._bootstrap_servers,
            "topic": self._topic,
            "delivered_count": self._delivered_count,
            "failed_count": self._delivery_errors,
            "pending_count": self._pending_count,
            "producer_active": self._producer is not None,
        }
