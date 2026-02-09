"""Kafka utilities for producer and consumer operations.

This module provides helper functions for Kafka operations with production-grade
settings optimized for trading workloads where durability is paramount.
"""

import json
from typing import Any

from confluent_kafka import Consumer, KafkaError, KafkaException, Producer
from confluent_kafka.admin import AdminClient, NewTopic

from src.common.config import KafkaSettings, get_settings
from src.common.logging_config import get_logger

logger = get_logger(__name__)


def create_producer(settings: KafkaSettings | None = None) -> Producer:
    """Create a Kafka producer with trading-grade durability settings.

    The producer is configured with:
    - acks=all: Wait for all replicas to acknowledge
    - enable.idempotence=true: Exactly-once producer semantics
    - retries: Maximum retries for transient failures
    - linger.ms: Small batch window for efficiency

    Args:
        settings: Kafka settings. If None, will use default settings.

    Returns:
        A configured Kafka producer instance.
    """
    if settings is None:
        settings = get_settings().kafka

    config = {
        "bootstrap.servers": settings.bootstrap_servers,
        # Durability settings (critical for trading)
        "acks": "all",  # Wait for all replicas
        "enable.idempotence": True,  # Exactly-once producer semantics
        "max.in.flight.requests.per.connection": 5,  # Required for idempotence
        # Retry settings
        "retries": 2147483647,  # Max retries (will honor delivery.timeout.ms)
        "delivery.timeout.ms": 120000,  # 2 minutes total timeout
        "retry.backoff.ms": 100,  # Backoff between retries
        # Batching settings (balance between latency and throughput)
        "linger.ms": 5,  # Wait up to 5ms to batch messages
        "batch.size": 16384,  # 16KB batch size
        # Compression
        "compression.type": "lz4",  # Good balance of speed and compression
        # Client identification
        "client.id": "trade-producer",
    }

    logger.info(
        "Creating Kafka producer",
        bootstrap_servers=settings.bootstrap_servers,
        acks="all",
        idempotence=True,
    )

    return Producer(config)


def create_consumer(
    settings: KafkaSettings | None = None,
    *,
    auto_commit: bool = False,
) -> Consumer:
    """Create a Kafka consumer with appropriate settings.

    The consumer is configured with manual offset commits for at-least-once
    semantics with idempotent downstream writes.

    Args:
        settings: Kafka settings. If None, will use default settings.
        auto_commit: Whether to enable auto-commit. Default False for
            manual commit after successful processing.

    Returns:
        A configured Kafka consumer instance.
    """
    if settings is None:
        settings = get_settings().kafka

    config = {
        "bootstrap.servers": settings.bootstrap_servers,
        "group.id": settings.consumer_group,
        # Offset management
        "auto.offset.reset": "earliest",  # Start from beginning if no offset
        "enable.auto.commit": auto_commit,
        # Processing settings
        "max.poll.interval.ms": 300000,  # 5 minutes max processing time
        "session.timeout.ms": 45000,  # 45 seconds session timeout
        "heartbeat.interval.ms": 15000,  # 15 seconds heartbeat
        # Fetch settings
        "fetch.min.bytes": 1,  # Don't wait for batches (low latency)
        "fetch.wait.max.ms": 500,  # Max wait for fetch response
        # Client identification
        "client.id": f"trade-consumer-{settings.consumer_group}",
    }

    logger.info(
        "Creating Kafka consumer",
        bootstrap_servers=settings.bootstrap_servers,
        consumer_group=settings.consumer_group,
        auto_commit=auto_commit,
    )

    return Consumer(config)


def create_admin_client(settings: KafkaSettings | None = None) -> AdminClient:
    """Create a Kafka admin client for topic management.

    Args:
        settings: Kafka settings. If None, will use default settings.

    Returns:
        A configured Kafka admin client instance.
    """
    if settings is None:
        settings = get_settings().kafka

    return AdminClient({"bootstrap.servers": settings.bootstrap_servers})


def ensure_topics_exist(
    settings: KafkaSettings | None = None,
    num_partitions: int = 6,
) -> None:
    """Ensure required Kafka topics exist.

    Creates the main trades topic and DLQ topic if they don't exist.
    Replication factor and min.insync.replicas are read from KafkaSettings.

    Args:
        settings: Kafka settings.
        num_partitions: Number of partitions for new topics.
    """
    if settings is None:
        settings = get_settings().kafka

    admin = create_admin_client(settings)

    topic_config = {
        "min.insync.replicas": str(settings.min_insync_replicas),
    }

    topics = [
        NewTopic(
            topic=settings.topic,
            num_partitions=num_partitions,
            replication_factor=settings.replication_factor,
            config=topic_config,
        ),
        NewTopic(
            topic=settings.dlq_topic,
            num_partitions=max(1, num_partitions // 2),  # Fewer partitions for DLQ
            replication_factor=settings.replication_factor,
            config=topic_config,
        ),
    ]

    futures = admin.create_topics(topics)

    for topic, future in futures.items():
        try:
            future.result()
            logger.info("Created topic", topic=topic)
        except KafkaException as e:
            if e.args[0].code() == KafkaError.TOPIC_ALREADY_EXISTS:
                logger.debug("Topic already exists", topic=topic)
            else:
                logger.error("Failed to create topic", topic=topic, error=str(e))
                raise


class DeliveryCallbackMixin:
    """Mixin providing Kafka delivery callback with Template Method pattern.

    Provides a standardized delivery callback that tracks errors and allows
    subclasses to customize behavior through hook methods.

    Attributes:
        _delivery_errors: Count of failed deliveries

    Example:
        ```python
        class MyProducer(DeliveryCallbackMixin):
            def _on_delivery_failure(self, err, msg):
                metrics.failures.inc()
                self._logger.error("Failed", error=str(err))

            def _on_delivery_success(self, msg):
                self._logger.debug("Delivered", offset=msg.offset())
        ```
    """

    _delivery_errors: int = 0

    def _delivery_callback(self, err: KafkaError | None, msg: Any) -> None:
        """Handle delivery confirmation (Template Method).

        Args:
            err: Error if delivery failed, None if successful.
            msg: The Kafka message object.
        """
        if err is not None:
            self._delivery_errors += 1
            self._on_delivery_failure(err, msg)
        else:
            self._on_delivery_success(msg)

    def _on_delivery_failure(self, _err: KafkaError, _msg: Any) -> None:
        """Hook for custom failure handling. Override in subclass."""
        pass

    def _on_delivery_success(self, _msg: Any) -> None:
        """Hook for custom success handling. Override in subclass."""
        pass


class MessageTooLargeError(Exception):
    """Raised when a serialized message exceeds Kafka's size limit."""

    def __init__(self, size_bytes: int, max_bytes: int):
        self.size_bytes = size_bytes
        self.max_bytes = max_bytes
        super().__init__(
            f"Message size {size_bytes} bytes exceeds limit of {max_bytes} bytes"
        )


# Kafka default message.max.bytes (broker-side limit)
DEFAULT_MAX_MESSAGE_BYTES = 1_048_576  # 1MB


def serialize_message(
    data: dict[str, Any],
    max_bytes: int = DEFAULT_MAX_MESSAGE_BYTES,
) -> bytes:
    """Serialize a message to JSON bytes with size validation.

    Validates message size before returning to catch oversized messages
    at the producer boundary rather than letting Kafka reject them.

    Args:
        data: Dictionary to serialize.
        max_bytes: Maximum allowed message size. Defaults to 1MB (Kafka default).

    Returns:
        UTF-8 encoded JSON bytes.

    Raises:
        MessageTooLargeError: If serialized message exceeds max_bytes.
    """
    serialized = json.dumps(data, default=str).encode("utf-8")
    if len(serialized) > max_bytes:
        raise MessageTooLargeError(len(serialized), max_bytes)
    return serialized


def deserialize_message(data: bytes) -> dict[str, Any]:
    """Deserialize JSON bytes to a dictionary.

    Args:
        data: UTF-8 encoded JSON bytes.

    Returns:
        Deserialized dictionary.

    Raises:
        json.JSONDecodeError: If the data is not valid JSON.
    """
    return json.loads(data.decode("utf-8"))
