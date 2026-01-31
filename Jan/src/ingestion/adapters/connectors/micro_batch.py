"""Micro-batch connector - collects events and flushes periodically (5-30s windows).

Wraps a streaming connector and batches its output.
"""

import asyncio
import time
from datetime import datetime, UTC
from typing import Any, AsyncIterator
from uuid import uuid4

from ingestion.adapters.connectors.base import BaseConnector
from ingestion.domain.models import SourceType
from ingestion.ports import IngestionPort, MetricsPort
from ingestion.resilience import CircuitBreaker, RetryPolicy


class MicroBatchConnector(BaseConnector):
    """Micro-batch connector - buffers events and flushes periodically.

    Can wrap any IngestionPort to add micro-batching behavior.

    Example:
        ```python
        # Wrap a WebSocket connector with micro-batching
        ws_connector = WebSocketConnector(...)

        connector = MicroBatchConnector(
            name="finnhub_microbatch",
            upstream=ws_connector,
            window_seconds=10,
            max_batch_size=1000,
        )

        async for batch in connector.stream_events():
            # batch is a list of events
            for event in batch:
                process(event)
        ```
    """

    def __init__(
        self,
        name: str,
        upstream: IngestionPort | None = None,
        window_seconds: int = 10,
        max_batch_size: int = 1000,
        min_batch_size: int = 1,
        flush_on_stop: bool = True,
        circuit_breaker: CircuitBreaker | None = None,
        retry_policy: RetryPolicy | None = None,
        metrics: MetricsPort | None = None,
    ):
        """Initialize micro-batch connector.

        Args:
            name: Connector identifier
            upstream: Optional upstream connector to wrap
            window_seconds: Time window for batching (5-30s recommended)
            max_batch_size: Maximum events per batch
            min_batch_size: Minimum events to emit a batch
            flush_on_stop: Whether to flush remaining events on stop
            circuit_breaker: Optional circuit breaker
            retry_policy: Optional retry policy
            metrics: Optional metrics port
        """
        super().__init__(
            name=name,
            source_type=SourceType.MICRO_BATCH,
            expected_latency_ms=window_seconds * 1000,
            circuit_breaker=circuit_breaker,
            retry_policy=retry_policy,
            metrics=metrics,
        )

        self._upstream = upstream
        self._window_seconds = window_seconds
        self._max_batch_size = max_batch_size
        self._min_batch_size = min_batch_size
        self._flush_on_stop = flush_on_stop

        self._buffer: list[dict[str, Any]] = []
        self._last_flush_time: float = time.monotonic()
        self._batch_count = 0
        self._event_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._upstream_task: asyncio.Task | None = None

    @property
    def buffer_size(self) -> int:
        """Get current buffer size."""
        return len(self._buffer)

    async def connect(self) -> None:
        """Connect upstream if configured."""
        self._logger.info(
            "Initializing micro-batch connector",
            window_seconds=self._window_seconds,
            max_batch_size=self._max_batch_size,
        )

        if self._upstream:
            # Start upstream in background
            self._upstream_task = asyncio.create_task(
                self._run_upstream()
            )

        self._last_flush_time = time.monotonic()

    async def disconnect(self) -> None:
        """Disconnect and optionally flush remaining events."""
        if self._upstream_task:
            self._upstream_task.cancel()
            try:
                await self._upstream_task
            except asyncio.CancelledError:
                pass

        if self._upstream:
            await self._upstream.disconnect()

    async def _run_upstream(self) -> None:
        """Run upstream connector and queue its events."""
        if not self._upstream:
            return

        try:
            async for event in self._upstream.stream_events():
                if not self._running:
                    break
                await self._event_queue.put(event)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self._logger.error("Upstream error", error=str(e))

    def _should_flush(self) -> bool:
        """Check if buffer should be flushed."""
        # Flush if max size reached
        if len(self._buffer) >= self._max_batch_size:
            return True

        # Flush if window elapsed and we have minimum events
        elapsed = time.monotonic() - self._last_flush_time
        if elapsed >= self._window_seconds and len(self._buffer) >= self._min_batch_size:
            return True

        return False

    def _flush_buffer(self) -> list[dict[str, Any]] | None:
        """Flush and return the buffer contents."""
        if not self._buffer:
            return None

        if len(self._buffer) < self._min_batch_size:
            return None

        batch = self._buffer.copy()
        self._buffer.clear()
        self._last_flush_time = time.monotonic()
        self._batch_count += 1

        return batch

    async def _collect_events(self) -> None:
        """Collect events from queue into buffer."""
        try:
            while True:
                # Non-blocking get
                event = self._event_queue.get_nowait()
                self._buffer.append(event)

                # Stop if max size reached
                if len(self._buffer) >= self._max_batch_size:
                    break

        except asyncio.QueueEmpty:
            pass

    async def _fetch_events(self) -> AsyncIterator[dict[str, Any]]:
        """Yield batches of events.

        Note: This yields dicts with a special "_batch" key containing
        the list of events. Consumers should check for this key.
        """
        while self._running:
            # Collect available events
            await self._collect_events()

            # Check if should flush
            if self._should_flush():
                batch = self._flush_buffer()
                if batch:
                    batch_id = f"{self._name}-{self._batch_count}-{uuid4().hex[:8]}"
                    self._logger.debug(
                        "Flushing batch",
                        batch_id=batch_id,
                        batch_size=len(batch),
                    )

                    # Yield batch as a special event
                    yield {
                        "_batch": batch,
                        "_batch_id": batch_id,
                        "_batch_size": len(batch),
                        "_batch_timestamp": datetime.now(UTC).isoformat(),
                    }

                    if self._metrics:
                        self._metrics.record_batch_processed(
                            self._name,
                            len(batch),
                            (time.monotonic() - self._last_flush_time) * 1000,
                        )

            # Small sleep to prevent tight loop
            await asyncio.sleep(0.1)

        # Final flush on stop
        if self._flush_on_stop and self._buffer:
            batch = self._buffer.copy()
            self._buffer.clear()
            if batch:
                batch_id = f"{self._name}-final-{uuid4().hex[:8]}"
                yield {
                    "_batch": batch,
                    "_batch_id": batch_id,
                    "_batch_size": len(batch),
                    "_batch_timestamp": datetime.now(UTC).isoformat(),
                }

    async def add_event(self, event: dict[str, Any]) -> None:
        """Manually add an event to the buffer.

        Use this when not using an upstream connector.
        """
        await self._event_queue.put(event)

    def add_event_nowait(self, event: dict[str, Any]) -> bool:
        """Manually add an event without waiting.

        Returns:
            True if added, False if queue full
        """
        try:
            self._event_queue.put_nowait(event)
            return True
        except asyncio.QueueFull:
            return False

    def get_stats(self) -> dict[str, Any]:
        """Get connector statistics."""
        stats = super().get_stats()
        stats.update({
            "window_seconds": self._window_seconds,
            "max_batch_size": self._max_batch_size,
            "min_batch_size": self._min_batch_size,
            "buffer_size": len(self._buffer),
            "batch_count": self._batch_count,
            "queue_size": self._event_queue.qsize(),
            "has_upstream": self._upstream is not None,
        })
        return stats
