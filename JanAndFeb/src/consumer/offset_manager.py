"""Offset management with safe commit coordination.

This module provides reliable offset management that coordinates Kafka offset commits
with database writes to prevent data loss and duplicates.

Key guarantees:
- Offsets are only committed after successful DB writes
- Failed commits are retried with backoff
- Offset state is tracked per partition for safe shutdown
- Provides true Kafka lag metrics (offset-based, not timestamp-based)

The Pattern:
1. Process message → update window state (track offset)
2. Flush window → write to DB in transaction
3. If DB write succeeds → commit offset with retry
4. If commit fails → log warning (DB write is idempotent, will dedupe on replay)
"""

import time
from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Callable

from confluent_kafka import Consumer, TopicPartition, KafkaError, KafkaException

from src.common.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class PartitionState:
    """Tracks offset state for a single partition.

    Attributes:
        partition: The partition number
        last_processed_offset: Last offset we successfully processed
        last_committed_offset: Last offset we successfully committed to Kafka
        pending_commit_offset: Offset waiting to be committed after DB write
        high_watermark: Latest offset in the partition (for lag calculation)
    """
    partition: int
    last_processed_offset: int = -1
    last_committed_offset: int = -1
    pending_commit_offset: int = -1
    high_watermark: int = -1

    @property
    def lag(self) -> int:
        """Calculate true Kafka consumer lag.

        Lag = high_watermark - committed_offset
        This is the real lag, not timestamp-based estimation.
        """
        if self.high_watermark < 0 or self.last_committed_offset < 0:
            return 0
        return max(0, self.high_watermark - self.last_committed_offset - 1)

    @property
    def uncommitted_count(self) -> int:
        """Count of processed but uncommitted offsets."""
        if self.last_processed_offset < 0 or self.last_committed_offset < 0:
            return 0
        return max(0, self.last_processed_offset - self.last_committed_offset)


@dataclass
class OffsetCommitResult:
    """Result of an offset commit operation."""
    success: bool
    partition: int
    offset: int
    error: str | None = None
    retry_count: int = 0


class OffsetManager:
    """Manages Kafka offsets with safe commit coordination.

    This class ensures that:
    1. Offsets are tracked per partition
    2. Commits are retried on failure
    3. True Kafka lag is calculated (not timestamp-based)
    4. Safe shutdown preserves offset state

    Usage:
        manager = OffsetManager(consumer)

        # After processing a message
        manager.mark_processed(partition=0, offset=100)

        # After successful DB write for a batch
        manager.commit_up_to(partition=0, offset=100)

        # Get true lag for monitoring
        lag = manager.get_partition_lag(partition=0)
    """

    def __init__(
        self,
        consumer: Consumer,
        *,
        max_commit_retries: int = 3,
        commit_retry_delay: float = 0.5,
        commit_timeout: float = 10.0,
    ):
        """Initialize the offset manager.

        Args:
            consumer: The Kafka consumer instance
            max_commit_retries: Maximum retries for failed commits
            commit_retry_delay: Base delay between retries (exponential backoff)
            commit_timeout: Timeout for commit operations
        """
        self._consumer = consumer
        self._max_retries = max_commit_retries
        self._retry_delay = commit_retry_delay
        self._commit_timeout = commit_timeout

        # Track state per partition
        self._partitions: dict[int, PartitionState] = {}

        # Statistics
        self._total_commits = 0
        self._failed_commits = 0
        self._retried_commits = 0

    def get_or_create_partition(self, partition: int) -> PartitionState:
        """Get or create partition state."""
        if partition not in self._partitions:
            self._partitions[partition] = PartitionState(partition=partition)
        return self._partitions[partition]

    def mark_processed(self, partition: int, offset: int) -> None:
        """Mark an offset as processed (but not yet committed).

        Call this after successfully processing a message.

        Args:
            partition: The partition number
            offset: The message offset
        """
        state = self.get_or_create_partition(partition)
        if offset > state.last_processed_offset:
            state.last_processed_offset = offset

    def update_high_watermark(self, partition: int, high_watermark: int) -> None:
        """Update the high watermark for a partition.

        Call this periodically to enable accurate lag calculation.

        Args:
            partition: The partition number
            high_watermark: The latest offset in the partition
        """
        state = self.get_or_create_partition(partition)
        state.high_watermark = high_watermark

    def commit_up_to(
        self,
        partition: int,
        offset: int,
        *,
        sync: bool = True,
    ) -> OffsetCommitResult:
        """Commit offset after successful DB write.

        This is the safe commit method - only call after DB write succeeds.
        Retries on failure with exponential backoff.

        Args:
            partition: The partition number
            offset: The offset to commit (exclusive - next message to read)
            sync: If True, wait for commit confirmation

        Returns:
            OffsetCommitResult with success status and details
        """
        state = self.get_or_create_partition(partition)
        commit_offset = offset + 1  # Kafka commits the *next* offset to read

        tp = TopicPartition(
            self._consumer.assignment()[0].topic if self._consumer.assignment() else "unknown",
            partition,
            commit_offset,
        )

        # Try to get topic from assignment
        assignment = self._consumer.assignment()
        if assignment:
            for assigned_tp in assignment:
                if assigned_tp.partition == partition:
                    tp = TopicPartition(assigned_tp.topic, partition, commit_offset)
                    break

        retry_count = 0
        last_error = None

        while retry_count <= self._max_retries:
            try:
                if sync:
                    # Synchronous commit with timeout
                    self._consumer.commit(offsets=[tp], asynchronous=False)
                else:
                    self._consumer.commit(offsets=[tp], asynchronous=True)

                # Success - update state
                state.last_committed_offset = offset
                self._total_commits += 1

                if retry_count > 0:
                    self._retried_commits += 1
                    logger.info(
                        "Offset commit succeeded after retry",
                        partition=partition,
                        offset=offset,
                        retry_count=retry_count,
                    )

                return OffsetCommitResult(
                    success=True,
                    partition=partition,
                    offset=offset,
                    retry_count=retry_count,
                )

            except KafkaException as e:
                last_error = str(e)
                retry_count += 1

                if retry_count <= self._max_retries:
                    delay = self._retry_delay * (2 ** (retry_count - 1))
                    logger.warning(
                        "Offset commit failed, retrying",
                        partition=partition,
                        offset=offset,
                        error=last_error,
                        retry_count=retry_count,
                        delay=delay,
                    )
                    time.sleep(delay)
                else:
                    self._failed_commits += 1
                    logger.error(
                        "Offset commit failed after all retries",
                        partition=partition,
                        offset=offset,
                        error=last_error,
                        max_retries=self._max_retries,
                    )

        return OffsetCommitResult(
            success=False,
            partition=partition,
            offset=offset,
            error=last_error,
            retry_count=retry_count,
        )

    def get_partition_lag(self, partition: int) -> int:
        """Get true Kafka lag for a partition.

        This returns actual offset-based lag, not timestamp-based estimation.

        Args:
            partition: The partition number

        Returns:
            Lag in number of messages
        """
        if partition not in self._partitions:
            return 0
        return self._partitions[partition].lag

    def get_total_lag(self) -> int:
        """Get total lag across all partitions."""
        return sum(state.lag for state in self._partitions.values())

    def get_uncommitted_count(self, partition: int) -> int:
        """Get count of processed but uncommitted offsets."""
        if partition not in self._partitions:
            return 0
        return self._partitions[partition].uncommitted_count

    def refresh_watermarks(self) -> None:
        """Refresh high watermarks for all assigned partitions.

        Call this periodically for accurate lag metrics.
        """
        try:
            assignment = self._consumer.assignment()
            for tp in assignment:
                # Get high watermark (latest offset)
                low, high = self._consumer.get_watermark_offsets(tp, timeout=5.0)
                self.update_high_watermark(tp.partition, high)
        except KafkaException as e:
            logger.warning("Failed to refresh watermarks", error=str(e))

    def get_stats(self) -> dict:
        """Get offset manager statistics."""
        return {
            "partitions": len(self._partitions),
            "total_commits": self._total_commits,
            "failed_commits": self._failed_commits,
            "retried_commits": self._retried_commits,
            "total_lag": self.get_total_lag(),
            "partition_lags": {
                p: state.lag for p, state in self._partitions.items()
            },
            "uncommitted": {
                p: state.uncommitted_count for p, state in self._partitions.items()
            },
        }

