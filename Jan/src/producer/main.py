"""Trade producer entry point.

This module provides the main entry point for the trade event producer service.
It initializes logging, configuration, and runs the producer.
"""

import signal
import sys
from typing import NoReturn

from src.common.config import get_settings
from src.common.logging_config import bind_context, configure_logging, get_logger
from src.producer.kafka_producer import TradeProducer

# Global producer instance for signal handling
_producer: TradeProducer | None = None


def signal_handler(signum: int, frame: object) -> None:
    """Handle shutdown signals gracefully."""
    logger = get_logger(__name__)
    logger.info("Received shutdown signal", signal=signum)
    if _producer is not None:
        _producer.stop()
    sys.exit(0)


def main() -> NoReturn:
    """Main entry point for the trade producer."""
    global _producer

    # Load settings and configure logging
    settings = get_settings()
    configure_logging(settings)

    # Bind service context to all log messages
    bind_context(
        service="trade-producer",
        environment=settings.environment,
    )

    logger = get_logger(__name__)
    logger.info(
        "Starting trade producer service",
        kafka_servers=settings.kafka.bootstrap_servers,
        topic=settings.kafka.topic,
        rate=settings.producer.rate,
        burst_enabled=settings.producer.burst_enabled,
    )

    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Create and run the producer
    _producer = TradeProducer(
        kafka_settings=settings.kafka,
        producer_settings=settings.producer,
    )

    try:
        # Run indefinitely (or until signal)
        _producer.run()
    except Exception as e:
        logger.exception("Producer failed with error", error=str(e))
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
