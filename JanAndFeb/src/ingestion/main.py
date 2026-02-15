"""Ingestion service entry point.

Starts the multi-source data ingestion system with configured connectors.

Usage:
    python -m ingestion.main

Ingestion Modes:
    INGESTION_MODE=local      Use synthetic producer (no ingestion needed)
    INGESTION_MODE=realtime   Real-time APIs (WebSocket, SSE, Polling)
    INGESTION_MODE=batch      Batch file processing (CSV, Parquet)
    INGESTION_MODE=hybrid     Both real-time and batch sources

Environment Variables:
    WS_ENABLED=true           Enable WebSocket connector (Finnhub)
    SSE_ENABLED=true          Enable SSE connector (DexPaprika)
    POLLING_ENABLED=true      Enable Polling connector (ENTSO-E)
    WEBHOOK_ENABLED=true      Enable Webhook receiver
    MICROBATCH_ENABLED=true   Enable Micro-batch connector
    BATCH_ENABLED=true        Enable Batch file processor

    See src/common/config.py for full configuration options.
"""

import asyncio
import signal
import sys

import structlog

from src.common.config import get_settings, IngestionMode
from src.common.logging_config import configure_logging
from src.ingestion.manager import IngestionManager
from src.ingestion.factories import ConnectorFactory, AdapterFactory, ConnectorType
from src.ingestion.adapters.publishers import KafkaPublisher
from src.ingestion.adapters.infrastructure import PrometheusMetrics


logger = structlog.get_logger()


async def create_ingestion_manager(settings) -> IngestionManager:
    """Create and configure the ingestion manager.

    Args:
        settings: Application settings

    Returns:
        Configured IngestionManager instance
    """
    ingestion_settings = settings.ingestion

    # Create metrics if enabled
    metrics = None
    if ingestion_settings.metrics_enabled:
        metrics = PrometheusMetrics(
            port=ingestion_settings.metrics_port,
            namespace="ingestion",
        )

    # Create Kafka publisher
    publisher = KafkaPublisher(
        bootstrap_servers=settings.kafka.bootstrap_servers,
        topic=settings.kafka.topic,
    )

    # Create DLQ publisher if enabled
    dlq_publisher = None
    if ingestion_settings.dlq_enabled:
        dlq_publisher = KafkaPublisher(
            bootstrap_servers=settings.kafka.bootstrap_servers,
            topic=settings.kafka.dlq_topic,
        )

    # Create manager
    manager = IngestionManager(
        publisher=publisher,
        metrics=metrics,
        dlq_publisher=dlq_publisher,
    )

    # Add enabled connectors based on mode
    enabled_sources = ingestion_settings.get_enabled_sources()

    if not enabled_sources:
        logger.warning(
            "No sources enabled for current mode",
            mode=ingestion_settings.mode.value,
            hint=_get_mode_hint(ingestion_settings.mode),
        )
    else:
        for source in enabled_sources:
            try:
                connector_type = ConnectorType(source.source_type)
                adapter_name = _get_adapter_name(source.name)
                upstream_source = getattr(source, "upstream_source", None)

                manager.add_connector_from_config(
                    connector_type=connector_type,
                    config=source.to_connector_config(),
                    adapter_name=adapter_name,
                    upstream_source=upstream_source,
                )

                logger.info(
                    "Source configured",
                    name=source.name,
                    type=source.source_type,
                    adapter=adapter_name,
                    upstream=upstream_source,
                )

            except Exception as e:
                logger.error(
                    "Failed to configure source",
                    name=source.name,
                    error=str(e),
                )

    return manager


def _get_adapter_name(source_name: str) -> str | None:
    """Map source name to adapter name.

    Args:
        source_name: Name of the source

    Returns:
        Adapter name or None if no adapter
    """
    adapter_map = {
        "finnhub": "finnhub",
        "dexpaprika": "dexpaprika",
        "entsoe": "entsoe",
    }
    return adapter_map.get(source_name.lower())


def _get_mode_hint(mode: IngestionMode) -> str:
    """Get helpful hint for enabling sources in each mode."""
    hints = {
        IngestionMode.LOCAL: "Use synthetic producer instead (docker compose --profile local up)",
        IngestionMode.REALTIME: "Set WS_ENABLED=true, SSE_ENABLED=true, or POLLING_ENABLED=true",
        IngestionMode.BATCH: "Set BATCH_ENABLED=true and place files in data/imports/",
        IngestionMode.HYBRID: "Enable real-time sources (WS_*, SSE_*, POLLING_*) and/or BATCH_ENABLED",
    }
    return hints.get(mode, "Check INGESTION_MODE setting")


async def run_ingestion_service() -> None:
    """Run the ingestion service."""
    settings = get_settings()
    configure_logging(settings)

    ingestion_settings = settings.ingestion
    mode = ingestion_settings.mode

    logger.info(
        "Starting ingestion service",
        mode=mode.value,
        environment=settings.environment,
        kafka_brokers=settings.kafka.bootstrap_servers,
        metrics_port=ingestion_settings.metrics_port,
    )

    # Check if ingestion is needed for this mode
    if not ingestion_settings.is_ingestion_needed():
        logger.info(
            "Ingestion not needed for LOCAL mode",
            suggestion="Use synthetic producer: docker compose --profile local up",
        )
        logger.info(
            "Available modes",
            local="Synthetic producer (default)",
            realtime="Real-time APIs (WebSocket, SSE, Polling)",
            batch="Batch file processing",
            hybrid="Real-time + Batch",
        )
        return

    # Create manager
    manager = await create_ingestion_manager(settings)

    # Setup signal handlers
    shutdown_event = asyncio.Event()

    def signal_handler(sig: signal.Signals) -> None:
        logger.info("Received shutdown signal", signal=sig.name)
        shutdown_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, lambda s=sig: signal_handler(s))
        except NotImplementedError:
            # Windows doesn't support add_signal_handler
            signal.signal(sig, lambda s, f: signal_handler(signal.Signals(s)))

    # Check if we have any connectors - fail gracefully instead of crashing
    if not manager._connectors:
        logger.warning(
            "No connectors configured - service will idle",
            mode=mode.value,
            hint=_get_mode_hint(mode),
        )

        # Start metrics server anyway so health checks work
        if manager._metrics:
            manager._metrics.start_server()
            logger.info(
                "Metrics server started (no connectors)",
                port=ingestion_settings.metrics_port,
            )

        # Wait gracefully, logging periodic reminders
        reminder_interval = 60  # seconds
        while not shutdown_event.is_set():
            try:
                await asyncio.wait_for(shutdown_event.wait(), timeout=reminder_interval)
            except asyncio.TimeoutError:
                logger.warning(
                    "Still waiting - no connectors configured",
                    mode=mode.value,
                    hint=_get_mode_hint(mode),
                )
        return

    # Start manager with connectors
    try:
        await manager.start()

        logger.info(
            "Ingestion service started",
            mode=mode.value,
            connectors=len(manager._connectors),
            sources=[c.name for c, _, _ in manager._connectors],
        )

        # Wait for shutdown signal
        await shutdown_event.wait()

    except Exception as e:
        logger.error("Ingestion service error", error=str(e))
        raise

    finally:
        logger.info("Shutting down ingestion service")
        await manager.stop()
        logger.info("Ingestion service stopped")


def main() -> None:
    """Main entry point."""
    try:
        asyncio.run(run_ingestion_service())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error("Fatal error", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
