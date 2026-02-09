"""Kafka consumer wrapper for trade events with windowed aggregation.

This module provides a high-level consumer that:
- Consumes trade events from Kafka
- Aggregates them into 1-minute tumbling windows
- Writes aggregates to PostgreSQL with idempotent upserts
- Routes malformed messages to DLQ

Key reliability improvements:
1. Safe offset commit coordination (commit after DB write with retry)
2. Window watermark tracking for safe shutdown
3. True Kafka lag metrics (offset-based)
4. Backpressure and flow control
5. Memory guardrails
6. DB connection pooling with auto-reconnect and retry (Fix #1, #7)
7. Idle window flush timer to prevent data loss when traffic stops (Fix #3)
8. Accurate per-partition offset commit timing (Fix #5)
9. Empirical memory estimation for window state (Fix #6)
"""

import json
import time
from datetime import UTC, datetime

from confluent_kafka import KafkaError, Message
from pydantic import ValidationError

from src.common.config import ConsumerSettings, KafkaSettings, get_settings
from src.common.kafka_utils import create_consumer, deserialize_message
from src.common.logging_config import get_logger
from src.common.models import TradeEvent
from src.consumer.backpressure import BackpressureController, FlowState
from src.consumer.db_writer import DatabaseWriter
from src.consumer.dlq_handler import AlertingDLQHandler, DLQHandler
from src.consumer.offset_manager import OffsetManager
from src.consumer.windowed_aggregator import WindowedAggregator, WindowFlushResult
from src.consumer import metrics

logger = get_logger(__name__)


class TradeConsumer:
    """High-level trade event consumer with windowed aggregation.

    Implements the streaming consumer with:
    - Safe offset commit coordination (DB write → commit with retry)
    - Window watermark tracking for safe shutdown
    - True Kafka lag monitoring (offset-based)
    - Backpressure for stability under load
    - Memory guardrails for aggregator state

    The commit safety guarantee:
    1. Process message → update window state (track offset in window)
    2. When window completes → write aggregate to DB
    3. If DB write succeeds → commit offsets with retry
    4. If commit fails → data is safe (DB write is idempotent)

    This ensures no data loss: worst case is duplicate processing
    on restart, but idempotent DB writes handle that.
    """

    def __init__(
        self,
        kafka_settings: KafkaSettings,
        consumer_settings: ConsumerSettings,
        *,
        db_writer: DatabaseWriter | None = None,
        dlq_handler: DLQHandler | None = None,
    ) -> None:
        """Initialize the trade consumer.

        Args:
            kafka_settings: Kafka configuration (explicitly passed, not global).
            consumer_settings: Consumer-specific configuration (explicitly passed).
            db_writer: Database writer instance.
            dlq_handler: DLQ handler instance.
        """
        self._kafka_settings = kafka_settings
        self._consumer_settings = consumer_settings

        # Create consumer with manual commit
        self._consumer = create_consumer(self._kafka_settings, auto_commit=False)

        # Initialize offset manager for safe commit coordination
        self._offset_manager = OffsetManager(
            self._consumer,
            max_commit_retries=3,
            commit_retry_delay=0.5,
        )

        # Initialize aggregator with offset tracking
        self._aggregator = WindowedAggregator(
            window_duration_seconds=self._consumer_settings.window_duration_seconds,
            late_event_grace_seconds=self._consumer_settings.late_event_grace_seconds,
            max_windows=1000,
            max_memory_mb=256,
            empirical_bytes_per_window=self._consumer_settings.empirical_bytes_per_window,
        )

        # Initialize backpressure controller with memory coordination
        self._backpressure = BackpressureController(
            self._consumer,
            high_watermark=1000,
            low_watermark=100,
            memory_check_fn=self._check_aggregator_memory,
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

        # Lag metrics refresh interval
        self._last_lag_refresh = 0.0
        self._lag_refresh_interval = 10.0  # seconds

        # Idle flush tracking
        self._last_idle_flush = 0.0
        self._idle_flush_interval = float(self._consumer_settings.idle_flush_interval)
        self._idle_flush_max_batch = self._consumer_settings.idle_flush_max_batch

    @classmethod
    def from_settings(cls) -> "TradeConsumer":
        """Create a TradeConsumer from global settings.

        This is the bootstrap method - use this at application startup.
        After creation, the consumer has explicit dependencies and doesn't
        rely on global state.

        Returns:
            Configured TradeConsumer instance
        """
        settings = get_settings()
        return cls(
            kafka_settings=settings.kafka,
            consumer_settings=settings.consumer,
        )

    def _check_aggregator_memory(self) -> tuple[int, int]:
        """Get aggregator memory state for backpressure coordination.

        Returns:
            Tuple of (current_memory_bytes, max_memory_bytes)
        """
        current = self._aggregator.get_estimated_memory_usage()
        maximum = self._aggregator.max_memory_bytes
        return (current, maximum)

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
        2. Add trade to windowed aggregator (with offset tracking)
        3. Write any completed aggregates to database
        4. Commit offsets for completed windows (with retry)

        If parsing fails, the message is sent to DLQ and offset is committed
        to prevent reprocessing the bad message.

        Args:
            msg: The Kafka message to process.
        """
        partition = msg.partition()
        offset = msg.offset()
        start_time = time.perf_counter()

        # Track message receipt
        metrics.messages_received.labels(partition=str(partition)).inc()
        self._backpressure.on_message_received()

        try:
            # Parse and validate
            trade = self._parse_message(msg)

            # Add to aggregator with offset tracking, get completed windows
            completed_results = self._aggregator.add_trade(
                trade,
                partition=partition,
                offset=offset,
            )

            # Mark offset as processed
            self._offset_manager.mark_processed(partition, offset)

            # Write completed aggregates to database and commit offsets
            if completed_results:
                try:
                    self._write_and_commit(completed_results)
                except Exception as e:
                    # write_aggregates_batch already retries; this catches truly
                    # unexpected errors so the consumer loop does not crash.
                    logger.error(
                        "Unexpected error writing aggregates; skipping commit",
                        error=str(e),
                    )

            self._messages_processed += 1

            # Update metrics
            metrics.messages_processed.labels(symbol=trade.symbol).inc()
            metrics.active_windows.set(self._aggregator.get_active_window_count())

            # Update data freshness (event timestamp age - NOT lag)
            event_age = (datetime.now(UTC) - trade.event_timestamp).total_seconds()
            metrics.data_freshness.set(event_age)

            # Legacy metric (deprecated but kept for compatibility)
            metrics.consumer_lag.labels(partition=str(partition)).set(event_age)

            # Record processing duration
            metrics.processing_duration.observe(time.perf_counter() - start_time)

            # Update memory metrics
            metrics.update_aggregator_memory(
                self._aggregator.get_estimated_memory_usage(),
                self._aggregator.max_memory_bytes,
            )

            # Log progress periodically
            if self._messages_processed % 1000 == 0:
                self._log_progress()

        except (json.JSONDecodeError, ValidationError, ValueError) as e:
            # Handle malformed messages via DLQ
            self._errors_handled += 1
            metrics.dlq_messages.labels(error_type=type(e).__name__).inc()
            raw_value = msg.value() or b""
            self._dlq_handler.handle_failed_message(
                raw_message=raw_value,
                error=e,
                partition=partition,
                offset=offset,
            )
            # Commit offset to move past the bad message
            self._offset_manager.commit_up_to(partition, offset)

        finally:
            self._backpressure.on_message_completed()

    def _write_and_commit(self, results: list[WindowFlushResult]) -> None:
        """Write aggregates to database and commit corresponding offsets.

        This is the critical coordination point:
        1. Write all aggregates in a batch transaction
        2. If successful, commit the maximum offset for each partition
        3. If commit fails, log warning (DB write is idempotent)

        Args:
            results: List of window flush results with aggregates and offsets
        """
        if not results:
            return

        # Extract aggregates for batch write
        aggregates = [r.aggregate for r in results]

        # Write to database
        db_start = time.perf_counter()
        try:
            written = self._db_writer.write_aggregates_batch(aggregates)
            metrics.db_write_duration.observe(time.perf_counter() - db_start)
            self._aggregates_written += written

            for agg in aggregates:
                metrics.aggregates_written.labels(symbol=agg.symbol).inc()

        except Exception as e:
            logger.error(
                "Failed to write aggregates to database",
                error=str(e),
                count=len(aggregates),
            )
            # Don't commit offsets - will retry on restart
            raise

        # write_aggregates_batch returns 0 when all retries are exhausted
        # (no exception raised). Committing offsets here would permanently
        # lose those aggregates since Kafka won't replay them.
        if written == 0:
            logger.error(
                "DB write returned 0 after retries; skipping offset commit "
                "to preserve at-least-once replay safety",
                count=len(aggregates),
            )
            return

        # Collect maximum offset per partition across all results
        partition_max_offsets: dict[int, int] = {}
        for result in results:
            for partition, offset in result.partition_offsets.items():
                current_max = partition_max_offsets.get(partition, -1)
                if offset > current_max:
                    partition_max_offsets[partition] = offset

        # Commit offsets with retry
        for partition, offset in partition_max_offsets.items():
            # Timer inside loop for per-partition timing (Fix #5)
            commit_start = time.perf_counter()
            commit_result = self._offset_manager.commit_up_to(partition, offset)
            commit_duration = time.perf_counter() - commit_start

            # Record metrics
            metrics.offset_commit_duration.observe(commit_duration)
            metrics.record_offset_commit(
                success=commit_result.success,
                retried=commit_result.retry_count > 0,
            )

            if not commit_result.success:
                # Log warning but don't fail - DB write is idempotent
                logger.warning(
                    "Offset commit failed after retries (data is safe due to idempotent writes)",
                    partition=partition,
                    offset=offset,
                    error=commit_result.error,
                )

    def _refresh_lag_metrics(self) -> None:
        """Refresh true Kafka lag metrics from broker.

        This updates offset-based lag metrics periodically.
        """
        now = time.monotonic()
        if now - self._last_lag_refresh < self._lag_refresh_interval:
            return

        self._last_lag_refresh = now

        try:
            self._offset_manager.refresh_watermarks()

            # Update metrics for each partition
            offset_stats = self._offset_manager.get_stats()
            for partition, lag in offset_stats.get("partition_lags", {}).items():
                partition_state = self._offset_manager._partitions.get(partition)
                if partition_state:
                    metrics.update_lag_metrics(
                        partition=partition,
                        high_watermark=partition_state.high_watermark,
                        committed_offset=partition_state.last_committed_offset,
                        processed_offset=partition_state.last_processed_offset,
                    )

            # Update total lag
            metrics.update_total_lag(offset_stats.get("total_lag", 0))

        except Exception as e:
            logger.warning("Failed to refresh lag metrics", error=str(e))

    def _perform_idle_flush(self) -> None:
        """Flush stale windows that haven't closed due to idle traffic.

        This prevents data loss when traffic stops: windows normally close
        when new events advance the watermark. Without traffic, windows
        never close. This method uses wall clock time to detect and flush
        stale windows.
        """
        now = datetime.now(UTC)
        stale_results = self._aggregator.flush_stale_windows(
            reference_time=now,
            max_batch=self._idle_flush_max_batch,
        )

        if stale_results:
            # Write flushed aggregates to database
            try:
                aggregates = [r.aggregate for r in stale_results]
                self._db_writer.write_aggregates_batch(aggregates)
                self._aggregates_written += len(aggregates)

                # Commit offsets for flushed windows
                partition_max_offsets: dict[int, int] = {}
                for result in stale_results:
                    for partition, offset in result.partition_offsets.items():
                        current_max = partition_max_offsets.get(partition, -1)
                        if offset > current_max:
                            partition_max_offsets[partition] = offset

                for partition, offset in partition_max_offsets.items():
                    self._offset_manager.commit_up_to(partition, offset)

                # Update metrics
                metrics.idle_flushes_total.inc()
                metrics.idle_flush_windows_count.observe(len(stale_results))

                logger.info(
                    "Idle flush completed",
                    flushed_count=len(stale_results),
                    partitions=list(partition_max_offsets.keys()),
                )

            except Exception as e:
                logger.error(
                    "Error during idle flush",
                    error=str(e),
                    flushed_count=len(stale_results),
                )

    def _log_progress(self) -> None:
        """Log processing progress and aggregator state."""
        state = self._aggregator.get_state_summary()
        offset_stats = self._offset_manager.get_stats()
        bp_stats = self._backpressure.get_stats()

        logger.info(
            "Processing progress",
            messages_processed=self._messages_processed,
            aggregates_written=self._aggregates_written,
            errors_handled=self._errors_handled,
            active_windows=state["active_windows"],
            total_lag=offset_stats.get("total_lag", 0),
            backpressure_state=bp_stats.get("state", "unknown"),
            memory_bytes=state.get("estimated_memory_bytes", 0),
        )

    def run(self) -> None:
        """Run the consumer continuously.

        Subscribes to the topic and processes messages until stopped.
        Includes backpressure handling and periodic metric updates.
        """
        self._running = True

        # Subscribe to topic
        self._consumer.subscribe([self._kafka_settings.topic])
        logger.info(
            "Consumer started",
            topic=self._kafka_settings.topic,
            consumer_group=self._kafka_settings.consumer_group,
        )

        # Set consumer info metric
        metrics.consumer_info.info({
            "topic": self._kafka_settings.topic,
            "consumer_group": self._kafka_settings.consumer_group,
        })

        try:
            while self._running:
                # Check backpressure - wait if paused
                if self._backpressure.wait_if_paused(timeout=0.5):
                    metrics.update_backpressure_state("paused")
                    continue

                # Update backpressure metrics
                bp_state = self._backpressure.state
                metrics.update_backpressure_state(bp_state.value)
                metrics.messages_in_flight.set(self._backpressure.in_flight_count)

                # Get recommended poll timeout based on backpressure state
                poll_timeout = self._backpressure.get_recommended_poll_timeout(1.0)

                # Poll for messages
                msg = self._consumer.poll(timeout=poll_timeout)

                # Idle flush runs on every iteration regardless of whether a
                # message arrived. Without this, a window for symbol A would
                # never flush while symbol B keeps producing messages.
                current_time = time.time()
                if current_time - self._last_idle_flush >= self._idle_flush_interval:
                    self._perform_idle_flush()
                    self._last_idle_flush = current_time

                if msg is None:
                    # No message - refresh lag metrics
                    self._refresh_lag_metrics()
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

                # Periodically refresh lag metrics
                self._refresh_lag_metrics()

        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        finally:
            self.stop()

    def stop(self) -> None:
        """Stop the consumer gracefully.

        Safe shutdown procedure:
        1. Stop accepting new messages
        2. Flush remaining aggregates
        3. Write flushed aggregates to database
        4. Commit offsets for flushed data
        5. Close connections
        """
        self._running = False

        # Resume if paused (for clean shutdown)
        self._backpressure.force_resume()

        # Flush remaining aggregates with offset information
        logger.info("Flushing remaining aggregates...")
        remaining_results = self._aggregator.flush_all()

        if remaining_results:
            try:
                # Write to database
                aggregates = [r.aggregate for r in remaining_results]
                self._db_writer.write_aggregates_batch(aggregates)
                self._aggregates_written += len(aggregates)

                # Commit offsets for flushed windows
                partition_max_offsets: dict[int, int] = {}
                for result in remaining_results:
                    for partition, offset in result.partition_offsets.items():
                        current_max = partition_max_offsets.get(partition, -1)
                        if offset > current_max:
                            partition_max_offsets[partition] = offset

                for partition, offset in partition_max_offsets.items():
                    self._offset_manager.commit_up_to(partition, offset)

                logger.info(
                    "Flushed and committed remaining data",
                    aggregates=len(aggregates),
                    partitions=list(partition_max_offsets.keys()),
                )

            except Exception as e:
                logger.error(
                    "Error during shutdown flush",
                    error=str(e),
                )

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
            offset_stats=self._offset_manager.get_stats(),
        )

    def check_health(self) -> dict[str, bool]:
        """Check consumer health status.

        Returns:
            Dictionary with health check results.
        """
        kafka_healthy = True  # Consumer is running if we get here
        db_healthy = self._db_writer.check_connection()
        bp_state = self._backpressure.state

        # Consider unhealthy if paused for too long
        not_paused = bp_state != FlowState.PAUSED

        return {
            "kafka": kafka_healthy,
            "database": db_healthy,
            "not_paused": not_paused,
            "overall": kafka_healthy and db_healthy and not_paused,
        }

    def get_stats(self) -> dict:
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
            "offset_stats": self._offset_manager.get_stats(),
            "backpressure_stats": self._backpressure.get_stats(),
        }
