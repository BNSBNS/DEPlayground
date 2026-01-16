"""Trade consumer entry point.

This module provides the main entry point for the streaming consumer service.
It initializes logging, configuration, and runs the consumer.
"""

import signal
import sys
from typing import NoReturn

from src.common.config import get_settings
from src.common.logging_config import bind_context, configure_logging, get_logger
from src.consumer.kafka_consumer import TradeConsumer

# Global consumer instance for signal handling
_consumer: TradeConsumer | None = None


def signal_handler(signum: int, frame: object) -> None:
    """Handle shutdown signals gracefully."""
    logger = get_logger(__name__)
    logger.info("Received shutdown signal", signal=signum)
    if _consumer is not None:
        _consumer.stop()
    sys.exit(0)


def main() -> NoReturn:
    """Main entry point for the trade consumer."""
    global _consumer

    # Load settings and configure logging
    settings = get_settings()
    configure_logging(settings)

    # Bind service context to all log messages
    bind_context(
        service="trade-consumer",
        environment=settings.environment,
        consumer_group=settings.kafka.consumer_group,
    )

    logger = get_logger(__name__)
    logger.info(
        "Starting trade consumer service",
        kafka_servers=settings.kafka.bootstrap_servers,
        topic=settings.kafka.topic,
        consumer_group=settings.kafka.consumer_group,
        window_duration=settings.consumer.window_duration_seconds,
    )

    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Create and run the consumer
    _consumer = TradeConsumer(
        kafka_settings=settings.kafka,
        consumer_settings=settings.consumer,
    )

    try:
        # Run until stopped
        _consumer.run()
    except Exception as e:
        logger.exception("Consumer failed with error", error=str(e))
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
