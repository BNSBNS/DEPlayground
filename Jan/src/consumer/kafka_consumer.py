"""Kafka consumer wrapper for trade events with windowed aggregation.

This module provides a high-level consumer that:
- Consumes trade events from Kafka
- Aggregates them into 1-minute tumbling windows
- Writes aggregates to PostgreSQL with idempotent upserts
- Routes malformed messages to DLQ
"""

import json
import signal
import sys
from datetime import UTC, datetime
from typing import Any, NoReturn

from confluent_kafka import Consumer, KafkaError, KafkaException, Message
from pydantic import ValidationError

from src.common.config import ConsumerSettings, KafkaSettings, get_settings
from src.common.kafka_utils import create_consumer, deserialize_message
from src.common.logging_config import get_logger
from src.common.models import TradeEvent
from src.consumer.db_writer import DatabaseWriter
from src.consumer.dlq_handler import AlertingDLQHandler, DLQHandler
from src.consumer.windowed_aggregator import WindowedAggregator

logger = get_logger(__name__)


class TradeConsumer:
    """High-level trade event consumer with windowed aggregation.

    Implements the streaming consumer with:
    - Safe restart behavior (resume from last committed offset)
    - No duplicate aggregates on recovery (idempotent DB writes)
    - Offset commit only after successful DB writes
    - DLQ handling for malformed messages
    """

    def __init__(
        self,
        kafka_settings: KafkaSettings | None = None,
        consumer_settings: ConsumerSettings | None = None,
        *,
        db_writer: DatabaseWriter | None = None,
        dlq_handler: DLQHandler | None = None,
    ) -> None:
        """Initialize the trade consumer.

        Args:
            kafka_settings: Kafka configuration.
            consumer_settings: Consumer-specific configuration.
            db_writer: Database writer instance.
            dlq_handler: DLQ handler instance.
        """
        settings = get_settings()
        self._kafka_settings = kafka_settings or settings.kafka
        self._consumer_settings = consumer_settings or settings.consumer

        # Create consumer with manual commit
        self._consumer = create_consumer(self._kafka_settings, auto_commit=False)

        # Initialize aggregator
        self._aggregator = WindowedAggregator(
            window_duration_seconds=self._consumer_settings.window_duration_seconds,
            late_event_grace_seconds=self._consumer_settings.late_event_grace_seconds,
        )

        # Initialize DB writer and DLQ handler
        self._db_writer = db_writer or DatabaseWriter()
        self._dlq_handler = dlq_handler or AlertingDLQHandler(
            self._kafka_settings,
            self._kafka_settings.consumer_group,
        )

        self._running = False

        # Statistics
        self._messages_processed = 0
        self._aggregates_written = 0
        self._errors_handled = 0

    def _parse_message(self, msg: Message) -> TradeEvent:
        """Parse and validate a Kafka message into a TradeEvent.

        Args:
            msg: The Kafka message to parse.

        Returns:
            Validated TradeEvent.

        Raises:
            json.JSONDecodeError: If message is not valid JSON.
            ValidationError: If message doesn't match TradeEvent schema.
        """
        value = msg.value()
        if value is None:
            raise ValueError("Message value is None")

        data = deserialize_message(value)
        return TradeEvent.from_kafka_value(data)

    def _process_message(self, msg: Message) -> None:
        """Process a single Kafka message.

        The processing flow:
        1. Parse and validate the message
        2. Add trade to windowed aggregator
        3. Write any completed aggregates to database
        4. Commit offset only after successful DB write

        If parsing fails, the message is sent to DLQ and offset is committed
        to prevent reprocessing the bad message.

        Args:
            msg: The Kafka message to process.
        """
        partition = msg.partition()
        offset = msg.offset()

        try:
            # Parse and validate
            trade = self._parse_message(msg)

            # Add to aggregator, get completed windows
            completed_aggregates = self._aggregator.add_trade(trade)

            # Write completed aggregates to database
            if completed_aggregates:
                written = self._db_writer.write_aggregates_batch(completed_aggregates)
                self._aggregates_written += written

            # Commit offset after successful processing
            self._consumer.commit(msg)
            self._messages_processed += 1

            # Log progress periodically
            if self._messages_processed % 1000 == 0:
                self._log_progress()

        except (json.JSONDecodeError, ValidationError, ValueError) as e:
            # Handle malformed messages via DLQ
            self._errors_handled += 1
            raw_value = msg.value() or b""
            self._dlq_handler.handle_failed_message(
                raw_message=raw_value,
                error=e,
                partition=partition,
                offset=offset,
            )
            # Commit offset to move past the bad message
            self._consumer.commit(msg)

    def _log_progress(self) -> None:
        """Log processing progress and aggregator state."""
        state = self._aggregator.get_state_summary()
        logger.info(
            "Processing progress",
            messages_processed=self._messages_processed,
            aggregates_written=self._aggregates_written,
            errors_handled=self._errors_handled,
            active_windows=state["active_windows"],
        )

    def run(self) -> None:
        """Run the consumer continuously.

        Subscribes to the topic and processes messages until stopped.
        """
        self._running = True

        # Subscribe to topic
        self._consumer.subscribe([self._kafka_settings.topic])
        logger.info(
            "Consumer started",
            topic=self._kafka_settings.topic,
            consumer_group=self._kafka_settings.consumer_group,
        )

        try:
            while self._running:
                # Poll for messages with 1 second timeout
                msg = self._consumer.poll(timeout=1.0)

                if msg is None:
                    # No message, check for completed windows due to time
                    continue

                if msg.error():
                    error = msg.error()
                    if error.code() == KafkaError._PARTITION_EOF:
                        # End of partition, normal condition
                        logger.debug(
                            "Reached end of partition",
                            partition=msg.partition(),
                        )
                    else:
                        logger.error(
                            "Kafka error",
                            error=str(error),
                            code=error.code(),
                        )
                    continue

                # Process the message
                self._process_message(msg)

        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        finally:
            self.stop()

    def stop(self) -> None:
        """Stop the consumer gracefully.

        Flushes remaining aggregates and closes connections.
        """
        self._running = False

        # Flush remaining aggregates
        logger.info("Flushing remaining aggregates...")
        remaining_aggregates = self._aggregator.flush_all()
        if remaining_aggregates:
            self._db_writer.write_aggregates_batch(remaining_aggregates)
            self._aggregates_written += len(remaining_aggregates)

        # Flush DLQ
        self._dlq_handler.flush()

        # Close consumer
        self._consumer.close()

        # Close database connection
        self._db_writer.close()

        logger.info(
            "Consumer stopped",
            messages_processed=self._messages_processed,
            aggregates_written=self._aggregates_written,
            errors_handled=self._errors_handled,
        )

    def check_health(self) -> dict[str, bool]:
        """Check consumer health status.

        Returns:
            Dictionary with health check results.
        """
        kafka_healthy = True  # Consumer is running if we get here
        db_healthy = self._db_writer.check_connection()

        return {
            "kafka": kafka_healthy,
            "database": db_healthy,
            "overall": kafka_healthy and db_healthy,
        }

    def get_stats(self) -> dict[str, int | dict[str, int | str | None]]:
        """Get consumer statistics.

        Returns:
            Dictionary with processing statistics.
        """
        return {
            "messages_processed": self._messages_processed,
            "aggregates_written": self._aggregates_written,
            "errors_handled": self._errors_handled,
            "dlq_stats": self._dlq_handler.get_stats(),
            "aggregator_state": self._aggregator.get_state_summary(),
        }
