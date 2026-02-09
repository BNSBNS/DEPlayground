"""Ingestion Manager - orchestrates multiple data source connectors.

The manager coordinates:
- Starting/stopping connectors
- Processing events through pipelines
- Publishing to Kafka
- Error handling and DLQ
- Metrics collection
"""

import asyncio
from datetime import datetime, UTC
from typing import Any

import structlog

from ingestion.ports import IngestionPort, EventPublisherPort, MetricsPort
from ingestion.domain.models import EnrichedTradeEvent
from ingestion.pipeline.builder import Pipeline, PipelineBuilder
from ingestion.adapters.formats.base import DataAdapter
from ingestion.factories import ConnectorFactory, AdapterFactory, ConnectorType


logger = structlog.get_logger()


class IngestionManager:
    """Orchestrates multiple data source connectors.

    Manages the lifecycle of connectors and coordinates event processing.

    Example:
        ```python
        manager = IngestionManager(
            publisher=KafkaPublisher(...),
            metrics=PrometheusMetrics(...),
        )

        # Add connectors
        manager.add_connector(websocket_connector, adapter=FinnhubAdapter())
        manager.add_connector(sse_connector, adapter=DexPaprikaAdapter())

        # Start all connectors
        await manager.start()

        # Wait for shutdown signal
        await manager.wait_for_shutdown()

        # Stop gracefully
        await manager.stop()
        ```
    """

    def __init__(
        self,
        publisher: EventPublisherPort,
        metrics: MetricsPort | None = None,
        dlq_publisher: EventPublisherPort | None = None,
    ):
        """Initialize ingestion manager.

        Args:
            publisher: Event publisher (e.g., Kafka)
            metrics: Optional metrics collector
            dlq_publisher: Optional dead letter queue publisher
        """
        self._publisher = publisher
        self._metrics = metrics
        self._dlq_publisher = dlq_publisher

        self._connectors: list[tuple[IngestionPort, Pipeline, DataAdapter | None]] = []
        self._tasks: list[asyncio.Task] = []
        self._running = False
        self._shutdown_event = asyncio.Event()

        self._total_events = 0
        self._total_errors = 0
        self._start_time: datetime | None = None

        self._logger = logger.bind(component="ingestion_manager")

    def add_connector(
        self,
        connector: IngestionPort,
        adapter: DataAdapter | None = None,
        pipeline: Pipeline | None = None,
    ) -> None:
        """Add a connector to manage.

        Args:
            connector: Data source connector
            adapter: Optional data format adapter
            pipeline: Optional processing pipeline (uses default if None)
        """
        if pipeline is None:
            # Build default pipeline
            pipeline = Pipeline(
                PipelineBuilder()
                .add_validation(strict=True)
                .add_transformation(adapter=adapter)
                .add_enrichment()
                .add_deduplication(cache_size=50000)
                .build()
            )

        self._connectors.append((connector, pipeline, adapter))
        self._logger.info(
            "Connector added",
            connector=connector.name,
            source_type=connector.source_type,
            has_adapter=adapter is not None,
        )

    def add_connector_from_config(
        self,
        connector_type: ConnectorType,
        config: dict[str, Any],
        adapter_name: str | None = None,
    ) -> None:
        """Add a connector from configuration.

        Args:
            connector_type: Type of connector
            config: Connector configuration
            adapter_name: Optional adapter name
        """
        connector = ConnectorFactory.create(
            connector_type=connector_type,
            config=config,
            metrics=self._metrics,
        )

        adapter = None
        if adapter_name:
            adapter = AdapterFactory.get_or_default(adapter_name)

        self.add_connector(connector, adapter)

    async def _run_connector(
        self,
        connector: IngestionPort,
        pipeline: Pipeline,
        adapter: DataAdapter | None,
    ) -> None:
        """Run a single connector with its pipeline.

        Args:
            connector: Data source connector
            pipeline: Processing pipeline
            adapter: Optional data format adapter. When provided, transforms raw
                events from the connector's source-specific format into
                EnrichedTradeEvent instances before pipeline processing.
                If None, raw events are passed directly to the pipeline.
        """
        self._logger.info(
            "Starting connector",
            connector=connector.name,
            adapter=adapter.__class__.__name__ if adapter else None,
        )

        try:
            async for raw_event in connector.stream_events():
                if not self._running:
                    break

                try:
                    # Unwrap batch envelopes: batch connectors yield
                    # {"_batch": [record, ...], ...} for I/O efficiency.
                    # Each individual record is processed separately.
                    if isinstance(raw_event, dict) and "_batch" in raw_event:
                        raw_items = raw_event["_batch"]
                    else:
                        raw_items = [raw_event]

                    for raw_item in raw_items:
                        # Transform through adapter if available
                        if adapter:
                            events_to_process = adapter.safe_transform(raw_item)
                            if not events_to_process:
                                self._logger.debug(
                                    "Adapter returned no events",
                                    connector=connector.name,
                                    adapter=adapter.__class__.__name__,
                                )
                                continue
                        else:
                            events_to_process = [raw_item]

                        # Process each transformed event through pipeline
                        for event_data in events_to_process:
                            event = await pipeline.process(event_data)

                            if event:
                                # Publish to Kafka
                                await self._publisher.publish(event)
                                self._total_events += 1

                                if self._metrics:
                                    latency = event.calculate_latency_ms() or 0
                                    self._metrics.record_event_ingested(
                                        connector.name,
                                        connector.source_type,
                                        latency,
                                    )
                                    self._metrics.record_event_published(
                                        connector.name,
                                        "kafka",
                                    )

                except Exception as e:
                    self._total_errors += 1
                    self._logger.error(
                        "Event processing failed",
                        connector=connector.name,
                        error=str(e),
                    )

                    if self._metrics:
                        self._metrics.record_error(
                            connector.name,
                            type(e).__name__,
                            str(e),
                        )

                    # Send to DLQ if configured
                    if self._dlq_publisher:
                        await self._send_to_dlq(raw_event, e, connector.name)

        except asyncio.CancelledError:
            self._logger.info("Connector cancelled", connector=connector.name)
            raise

        except Exception as e:
            self._logger.error(
                "Connector failed",
                connector=connector.name,
                error=str(e),
            )
            if self._metrics:
                self._metrics.record_error(
                    connector.name,
                    type(e).__name__,
                    str(e),
                )

    async def _send_to_dlq(
        self,
        raw_event: Any,
        error: Exception,
        source: str,
    ) -> None:
        """Send failed event to dead letter queue.

        Preserves the original event payload and error context for debugging
        and potential replay.
        """
        try:
            from ingestion.domain.models import SourceMetadata, SourceType
            import json

            # Extract symbol from raw_event if possible, otherwise use "UNKNOWN"
            symbol = "UNKNOWN"
            if isinstance(raw_event, dict):
                symbol = raw_event.get("symbol", raw_event.get("s", "UNKNOWN"))

            # Serialize raw_event to JSON for preservation
            try:
                raw_payload_json = json.dumps(raw_event) if raw_event else None
            except (TypeError, ValueError):
                # If can't serialize, store string representation
                raw_payload_json = str(raw_event) if raw_event else None

            # Create DLQ event with preserved context
            dlq_event = EnrichedTradeEvent(
                symbol=f"DLQ_{symbol}",  # Prefix to distinguish DLQ messages
                price=0,  # Dummy value (required field)
                volume=1,  # Dummy value (required field)
                side="BUY",  # Dummy value (required field)
                trader_id=source,
                event_timestamp=datetime.now(UTC),
                source_metadata=SourceMetadata(
                    source_type=SourceType.SYNTHETIC,
                    source_name=f"dlq_{source}",
                    ingestion_timestamp=datetime.now(UTC),
                    expected_latency_ms=0,
                ),
                # DLQ-specific fields with original context
                dlq_error_type=type(error).__name__,
                dlq_error_message=str(error)[:500],  # Truncate to field limit
                dlq_original_payload=raw_payload_json,
            )

            await self._dlq_publisher.publish(dlq_event)

            self._logger.info(
                "Sent failed event to DLQ",
                source=source,
                error_type=type(error).__name__,
                original_symbol=symbol,
            )

        except Exception as dlq_error:
            self._logger.error(
                "Failed to send to DLQ",
                original_error=str(error),
                dlq_error=str(dlq_error),
            )

    async def start(self) -> None:
        """Start all connectors."""
        if self._running:
            self._logger.warning("Manager already running")
            return

        self._running = True
        self._start_time = datetime.now(UTC)
        self._shutdown_event.clear()

        self._logger.info(
            "Starting ingestion manager",
            connector_count=len(self._connectors),
        )

        # Start metrics server if configured
        if self._metrics:
            self._metrics.start_server()

        # Start all connectors
        for connector, pipeline, adapter in self._connectors:
            task = asyncio.create_task(
                self._run_connector(connector, pipeline, adapter),
                name=f"connector_{connector.name}",
            )
            self._tasks.append(task)

        self._logger.info(
            "All connectors started",
            task_count=len(self._tasks),
        )

    async def stop(self) -> None:
        """Stop all connectors gracefully."""
        if not self._running:
            return

        self._logger.info("Stopping ingestion manager")
        self._running = False

        # Signal connectors to stop
        for connector, _, _ in self._connectors:
            connector.stop()

        # Cancel tasks
        for task in self._tasks:
            if not task.done():
                task.cancel()

        # Wait for tasks to complete
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

        # Flush publisher
        await self._publisher.flush()

        self._tasks.clear()
        self._shutdown_event.set()

        self._logger.info(
            "Ingestion manager stopped",
            total_events=self._total_events,
            total_errors=self._total_errors,
            uptime_seconds=(
                (datetime.now(UTC) - self._start_time).total_seconds()
                if self._start_time else 0
            ),
        )

    async def wait_for_shutdown(self) -> None:
        """Wait for shutdown signal."""
        await self._shutdown_event.wait()

    def get_status(self) -> dict[str, Any]:
        """Get manager status."""
        return {
            "running": self._running,
            "connector_count": len(self._connectors),
            "active_tasks": sum(1 for t in self._tasks if not t.done()),
            "total_events": self._total_events,
            "total_errors": self._total_errors,
            "start_time": self._start_time.isoformat() if self._start_time else None,
            "uptime_seconds": (
                (datetime.now(UTC) - self._start_time).total_seconds()
                if self._start_time else 0
            ),
            "connectors": [
                {
                    "name": c.name,
                    "type": c.source_type,
                    "connected": c.is_connected,
                    "stats": c.get_stats(),
                }
                for c, _, _ in self._connectors
            ],
        }

    def get_connector(self, name: str) -> IngestionPort | None:
        """Get a connector by name."""
        for connector, _, _ in self._connectors:
            if connector.name == name:
                return connector
        return None
