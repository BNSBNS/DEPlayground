"""Dead Letter Queue (DLQ) handler for failed messages.

This module implements the DLQ pattern to handle malformed or unparseable
messages without blocking the main processing pipeline.
"""

import json
from datetime import UTC, datetime
from typing import Any

from confluent_kafka import Producer

from src.common.config import KafkaSettings, get_settings
from src.common.kafka_utils import create_producer, serialize_message
from src.common.logging_config import get_logger
from src.common.models import DLQMessage

logger = get_logger(__name__)


class DLQHandler:
    """Dead Letter Queue handler for failed messages.

    When a message cannot be processed (validation error, malformed JSON, etc.),
    this handler:
    1. Wraps the message with error context
    2. Publishes to the DLQ topic for later investigation
    3. Logs the failure for monitoring/alerting

    This ensures the consumer can continue processing subsequent messages
    rather than getting stuck on a bad message.
    """

    def __init__(
        self,
        kafka_settings: KafkaSettings | None = None,
        consumer_group: str | None = None,
    ) -> None:
        """Initialize the DLQ handler.

        Args:
            kafka_settings: Kafka configuration with DLQ topic.
            consumer_group: Consumer group name for context.
        """
        settings = get_settings()
        self._kafka_settings = kafka_settings or settings.kafka
        self._consumer_group = consumer_group or self._kafka_settings.consumer_group
        self._producer: Producer | None = None

        # Statistics
        self._messages_sent = 0

    @property
    def producer(self) -> Producer:
        """Get or create the Kafka producer for DLQ."""
        if self._producer is None:
            self._producer = create_producer(self._kafka_settings)
        return self._producer

    def handle_failed_message(
        self,
        raw_message: bytes | str,
        error: Exception,
        partition: int,
        offset: int,
    ) -> DLQMessage:
        """Handle a failed message by sending to DLQ.

        Args:
            raw_message: The original message that failed processing.
            error: The exception that was raised.
            partition: Kafka partition the message came from.
            offset: Kafka offset of the message.

        Returns:
            The DLQMessage that was created and sent.
        """
        # Convert bytes to string if needed
        if isinstance(raw_message, bytes):
            try:
                message_str = raw_message.decode("utf-8")
            except UnicodeDecodeError:
                message_str = raw_message.hex()
        else:
            message_str = raw_message

        # Create DLQ message with context
        dlq_message = DLQMessage(
            original_message=message_str,
            error_type=type(error).__name__,
            error_message=str(error),
            failed_at=datetime.now(UTC),
            consumer_group=self._consumer_group,
            partition=partition,
            offset=offset,
        )

        # Publish to DLQ topic
        self._send_to_dlq(dlq_message)

        # Log for monitoring/alerting
        logger.warning(
            "Message sent to DLQ",
            error_type=dlq_message.error_type,
            error_message=dlq_message.error_message,
            partition=partition,
            offset=offset,
            consumer_group=self._consumer_group,
        )

        self._messages_sent += 1
        return dlq_message

    def _send_to_dlq(self, dlq_message: DLQMessage) -> None:
        """Send a message to the DLQ Kafka topic.

        Args:
            dlq_message: The DLQ message to send.
        """
        try:
            self.producer.produce(
                topic=self._kafka_settings.dlq_topic,
                key=f"{dlq_message.partition}:{dlq_message.offset}".encode("utf-8"),
                value=serialize_message(dlq_message.to_kafka_value()),
                callback=self._delivery_callback,
            )
            # Trigger delivery
            self.producer.poll(0)
        except Exception as e:
            # Log but don't raise - we don't want DLQ failures to block processing
            logger.error(
                "Failed to send message to DLQ",
                error=str(e),
                partition=dlq_message.partition,
                offset=dlq_message.offset,
            )

    def _delivery_callback(self, err: Exception | None, msg: Any) -> None:
        """Handle DLQ delivery confirmation."""
        if err is not None:
            logger.error(
                "DLQ message delivery failed",
                error=str(err),
            )
        else:
            logger.debug(
                "DLQ message delivered",
                topic=msg.topic(),
                partition=msg.partition(),
            )

    def flush(self, timeout: float = 5.0) -> int:
        """Flush pending DLQ messages.

        Args:
            timeout: Maximum time to wait for delivery.

        Returns:
            Number of messages still in queue after flush.
        """
        if self._producer is not None:
            return self._producer.flush(timeout=timeout)
        return 0

    def get_stats(self) -> dict[str, int]:
        """Get DLQ handler statistics.

        Returns:
            Dictionary with messages_sent count.
        """
        return {"messages_sent": self._messages_sent}


class AlertingDLQHandler(DLQHandler):
    """DLQ handler with alerting capabilities.

    Extends the base DLQ handler to trigger alerts when messages
    are sent to the DLQ, enabling on-call engineers to investigate.
    """

    def __init__(
        self,
        kafka_settings: KafkaSettings | None = None,
        consumer_group: str | None = None,
        *,
        alert_callback: Any | None = None,
        alert_threshold: int = 1,
    ) -> None:
        """Initialize the alerting DLQ handler.

        Args:
            kafka_settings: Kafka configuration.
            consumer_group: Consumer group name.
            alert_callback: Callable to invoke for alerts.
                           Signature: (dlq_message: DLQMessage) -> None
            alert_threshold: Number of DLQ messages before alerting.
        """
        super().__init__(kafka_settings, consumer_group)
        self._alert_callback = alert_callback
        self._alert_threshold = alert_threshold
        self._alert_count = 0

    def handle_failed_message(
        self,
        raw_message: bytes | str,
        error: Exception,
        partition: int,
        offset: int,
    ) -> DLQMessage:
        """Handle failed message with alerting.

        Args:
            raw_message: The original message that failed.
            error: The exception that was raised.
            partition: Kafka partition.
            offset: Kafka offset.

        Returns:
            The DLQMessage that was created.
        """
        dlq_message = super().handle_failed_message(
            raw_message, error, partition, offset
        )

        # Check if we should alert
        self._alert_count += 1
        if self._alert_count >= self._alert_threshold:
            self._trigger_alert(dlq_message)
            self._alert_count = 0  # Reset counter after alert

        return dlq_message

    def _trigger_alert(self, dlq_message: DLQMessage) -> None:
        """Trigger an alert for DLQ message.

        Args:
            dlq_message: The message that triggered the alert.
        """
        logger.error(
            "ALERT: DLQ threshold reached",
            threshold=self._alert_threshold,
            error_type=dlq_message.error_type,
            consumer_group=dlq_message.consumer_group,
        )

        if self._alert_callback:
            try:
                self._alert_callback(dlq_message)
            except Exception as e:
                logger.error("Alert callback failed", error=str(e))
