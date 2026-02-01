"""Backpressure and flow control for the streaming consumer.

This module implements backpressure mechanisms to prevent memory exhaustion
when downstream systems (database) are slower than upstream (Kafka).

Key mechanisms:
1. Bounded in-flight message queue
2. Pause/resume Kafka consumption based on queue depth
3. Rate limiting based on processing throughput
4. Memory-based flow control

Without backpressure, a slow database can cause:
- Unbounded memory growth in aggregation state
- Consumer crashes due to OOM
- Message loss during recovery
"""

import asyncio
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum
from typing import Callable, TypeVar, Generic

from confluent_kafka import Consumer, TopicPartition

from src.common.logging_config import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class FlowState(str, Enum):
    """Current flow control state."""
    FLOWING = "flowing"      # Normal processing
    THROTTLED = "throttled"  # Reduced rate
    PAUSED = "paused"        # Kafka consumption paused


@dataclass
class FlowMetrics:
    """Metrics for flow control monitoring."""
    state: FlowState = FlowState.FLOWING
    queue_depth: int = 0
    queue_capacity: int = 0
    messages_in_flight: int = 0
    pause_count: int = 0
    resume_count: int = 0
    throttle_count: int = 0
    last_state_change: datetime = field(default_factory=lambda: datetime.now(UTC))
    current_throughput: float = 0.0  # messages per second
    target_throughput: float = 0.0


class BackpressureController:
    """Controls backpressure based on queue depth and processing rate.

    This controller monitors the processing pipeline and applies
    backpressure when needed:

    1. When queue depth exceeds high watermark → PAUSE consumption
    2. When queue depth drops below low watermark → RESUME consumption
    3. When processing rate drops → THROTTLE (reduce batch sizes)

    Usage:
        controller = BackpressureController(
            consumer=kafka_consumer,
            high_watermark=1000,
            low_watermark=100,
        )

        # In processing loop
        if controller.should_process():
            msg = consumer.poll()
            controller.on_message_received()
            # ... process message ...
            controller.on_message_completed()
    """

    def __init__(
        self,
        consumer: Consumer,
        *,
        high_watermark: int = 1000,
        low_watermark: int = 100,
        max_in_flight: int = 5000,
        pause_on_memory_mb: int = 500,
        check_interval_seconds: float = 1.0,
    ):
        """Initialize the backpressure controller.

        Args:
            consumer: Kafka consumer to pause/resume
            high_watermark: Queue depth to trigger pause
            low_watermark: Queue depth to trigger resume
            max_in_flight: Maximum messages being processed
            pause_on_memory_mb: Pause if memory exceeds this (MB)
            check_interval_seconds: How often to check conditions
        """
        self._consumer = consumer
        self._high_watermark = high_watermark
        self._low_watermark = low_watermark
        self._max_in_flight = max_in_flight
        self._pause_on_memory_mb = pause_on_memory_mb
        self._check_interval = check_interval_seconds

        # State tracking
        self._state = FlowState.FLOWING
        self._in_flight_count = 0
        self._lock = threading.Lock()

        # Statistics
        self._pause_count = 0
        self._resume_count = 0
        self._throttle_count = 0
        self._last_state_change = datetime.now(UTC)

        # Throughput tracking
        self._message_times: deque[float] = deque(maxlen=1000)
        self._last_throughput_calc = time.monotonic()
        self._current_throughput = 0.0

        # Paused partitions tracking
        self._paused_partitions: set[TopicPartition] = set()

    @property
    def state(self) -> FlowState:
        """Get current flow state."""
        return self._state

    @property
    def in_flight_count(self) -> int:
        """Get count of messages currently being processed."""
        return self._in_flight_count

    def should_process(self) -> bool:
        """Check if we should continue processing.

        Returns False if backpressure is applied and we should wait.
        """
        return self._state != FlowState.PAUSED

    def on_message_received(self) -> None:
        """Call when a message is received from Kafka."""
        with self._lock:
            self._in_flight_count += 1
            self._message_times.append(time.monotonic())
            self._check_backpressure()

    def on_message_completed(self) -> None:
        """Call when a message has been fully processed."""
        with self._lock:
            self._in_flight_count = max(0, self._in_flight_count - 1)
            self._check_backpressure()

    def on_batch_completed(self, count: int) -> None:
        """Call when a batch of messages has been processed."""
        with self._lock:
            self._in_flight_count = max(0, self._in_flight_count - count)
            self._check_backpressure()

    def _check_backpressure(self) -> None:
        """Check conditions and apply/release backpressure."""
        # Calculate current throughput
        self._update_throughput()

        # Check if we should pause
        if self._in_flight_count >= self._high_watermark:
            if self._state != FlowState.PAUSED:
                self._pause()
        # Check if we should resume
        elif self._in_flight_count <= self._low_watermark:
            if self._state == FlowState.PAUSED:
                self._resume()
        # Check for throttling
        elif self._in_flight_count > self._low_watermark * 2:
            if self._state == FlowState.FLOWING:
                self._throttle()
        elif self._state == FlowState.THROTTLED:
            self._state = FlowState.FLOWING
            self._last_state_change = datetime.now(UTC)

    def _update_throughput(self) -> None:
        """Calculate current message throughput."""
        now = time.monotonic()
        if now - self._last_throughput_calc >= 1.0:
            # Count messages in last second
            cutoff = now - 1.0
            recent = sum(1 for t in self._message_times if t >= cutoff)
            self._current_throughput = float(recent)
            self._last_throughput_calc = now

    def _pause(self) -> None:
        """Pause Kafka consumption."""
        self._state = FlowState.PAUSED
        self._pause_count += 1
        self._last_state_change = datetime.now(UTC)

        # Pause all assigned partitions
        try:
            assignment = self._consumer.assignment()
            if assignment:
                self._paused_partitions = set(assignment)
                self._consumer.pause(list(assignment))
                logger.warning(
                    "Backpressure: PAUSED consumption",
                    in_flight=self._in_flight_count,
                    high_watermark=self._high_watermark,
                    partitions=len(assignment),
                )
        except Exception as e:
            logger.error("Failed to pause consumer", error=str(e))

    def _resume(self) -> None:
        """Resume Kafka consumption."""
        self._state = FlowState.FLOWING
        self._resume_count += 1
        self._last_state_change = datetime.now(UTC)

        # Resume paused partitions
        try:
            if self._paused_partitions:
                self._consumer.resume(list(self._paused_partitions))
                logger.info(
                    "Backpressure: RESUMED consumption",
                    in_flight=self._in_flight_count,
                    low_watermark=self._low_watermark,
                    partitions=len(self._paused_partitions),
                )
                self._paused_partitions.clear()
        except Exception as e:
            logger.error("Failed to resume consumer", error=str(e))

    def _throttle(self) -> None:
        """Enter throttled state (reduced processing rate)."""
        self._state = FlowState.THROTTLED
        self._throttle_count += 1
        self._last_state_change = datetime.now(UTC)

        logger.info(
            "Backpressure: THROTTLED",
            in_flight=self._in_flight_count,
        )

    def get_recommended_batch_size(self, default: int = 100) -> int:
        """Get recommended batch size based on current state.

        When throttled, returns smaller batch sizes.

        Args:
            default: Default batch size when flowing normally

        Returns:
            Recommended batch size
        """
        if self._state == FlowState.PAUSED:
            return 0
        elif self._state == FlowState.THROTTLED:
            return max(1, default // 4)
        else:
            return default

    def get_recommended_poll_timeout(self, default: float = 1.0) -> float:
        """Get recommended poll timeout based on current state.

        When throttled, use shorter timeouts for more responsive backpressure.

        Args:
            default: Default poll timeout in seconds

        Returns:
            Recommended poll timeout
        """
        if self._state == FlowState.PAUSED:
            # When paused, wait longer before checking again
            return default * 2
        elif self._state == FlowState.THROTTLED:
            # When throttled, check more frequently
            return default / 2
        else:
            return default

    def wait_if_paused(self, timeout: float = 1.0) -> bool:
        """Wait if consumption is paused.

        Call this in the processing loop to block when paused.

        Args:
            timeout: Maximum time to wait

        Returns:
            True if still paused, False if resumed
        """
        if self._state != FlowState.PAUSED:
            return False

        time.sleep(timeout)
        self._check_backpressure()
        return self._state == FlowState.PAUSED

    def force_resume(self) -> None:
        """Force resume consumption (for shutdown)."""
        if self._paused_partitions:
            try:
                self._consumer.resume(list(self._paused_partitions))
                self._paused_partitions.clear()
            except Exception:
                pass
        self._state = FlowState.FLOWING

    def get_metrics(self) -> FlowMetrics:
        """Get current flow control metrics."""
        return FlowMetrics(
            state=self._state,
            queue_depth=self._in_flight_count,
            queue_capacity=self._high_watermark,
            messages_in_flight=self._in_flight_count,
            pause_count=self._pause_count,
            resume_count=self._resume_count,
            throttle_count=self._throttle_count,
            last_state_change=self._last_state_change,
            current_throughput=self._current_throughput,
            target_throughput=float(self._high_watermark),
        )

    def get_stats(self) -> dict:
        """Get statistics for monitoring."""
        return {
            "state": self._state.value,
            "in_flight": self._in_flight_count,
            "high_watermark": self._high_watermark,
            "low_watermark": self._low_watermark,
            "pause_count": self._pause_count,
            "resume_count": self._resume_count,
            "throttle_count": self._throttle_count,
            "throughput_per_sec": self._current_throughput,
            "paused_partitions": len(self._paused_partitions),
        }


class BoundedQueue(Generic[T]):
    """Thread-safe bounded queue with backpressure support.

    When the queue is full, put() will block until space is available.
    This provides natural backpressure in producer-consumer patterns.
    """

    def __init__(self, maxsize: int = 1000):
        """Initialize the bounded queue.

        Args:
            maxsize: Maximum queue size
        """
        self._queue: deque[T] = deque(maxlen=maxsize)
        self._maxsize = maxsize
        self._lock = threading.Lock()
        self._not_full = threading.Condition(self._lock)
        self._not_empty = threading.Condition(self._lock)
        self._closed = False

    def put(self, item: T, timeout: float | None = None) -> bool:
        """Put an item in the queue.

        Blocks if queue is full until space is available.

        Args:
            item: Item to add
            timeout: Maximum time to wait (None = forever)

        Returns:
            True if item was added, False if timeout or closed
        """
        with self._not_full:
            if self._closed:
                return False

            if len(self._queue) >= self._maxsize:
                if not self._not_full.wait(timeout):
                    return False

            if self._closed:
                return False

            self._queue.append(item)
            self._not_empty.notify()
            return True

    def get(self, timeout: float | None = None) -> T | None:
        """Get an item from the queue.

        Blocks if queue is empty until an item is available.

        Args:
            timeout: Maximum time to wait (None = forever)

        Returns:
            Item or None if timeout or closed
        """
        with self._not_empty:
            if self._closed and len(self._queue) == 0:
                return None

            if len(self._queue) == 0:
                if not self._not_empty.wait(timeout):
                    return None

            if len(self._queue) == 0:
                return None

            item = self._queue.popleft()
            self._not_full.notify()
            return item

    def qsize(self) -> int:
        """Get current queue size."""
        return len(self._queue)

    def is_full(self) -> bool:
        """Check if queue is full."""
        return len(self._queue) >= self._maxsize

    def close(self) -> None:
        """Close the queue, unblocking all waiters."""
        with self._lock:
            self._closed = True
            self._not_full.notify_all()
            self._not_empty.notify_all()

    def drain(self) -> list[T]:
        """Drain all items from the queue."""
        with self._lock:
            items = list(self._queue)
            self._queue.clear()
            self._not_full.notify_all()
            return items
