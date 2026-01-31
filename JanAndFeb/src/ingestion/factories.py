"""Factory pattern for creating connectors and adapters.

Provides centralized creation of components based on configuration.
"""

from enum import Enum
from typing import Any

import structlog

from ingestion.ports import IngestionPort, MetricsPort
from ingestion.domain.models import SourceType
from ingestion.resilience import CircuitBreaker, RetryPolicy, RateLimiter


logger = structlog.get_logger()


class ConnectorType(str, Enum):
    """Connector type identifiers."""

    WEBSOCKET = "websocket"
    SSE = "sse"
    POLLING = "polling"
    WEBHOOK = "webhook"
    MICRO_BATCH = "micro_batch"
    BATCH = "batch"


class ConnectorFactory:
    """Factory for creating source connectors.

    Uses a registry pattern to map connector types to implementations.

    Example:
        ```python
        # Register connector
        @ConnectorFactory.register(ConnectorType.WEBSOCKET)
        class MyWebSocketConnector(IngestionPort):
            ...

        # Create connector
        connector = ConnectorFactory.create(
            ConnectorType.WEBSOCKET,
            config={"url": "wss://api.example.com"}
        )
        ```
    """

    _registry: dict[ConnectorType, type[IngestionPort]] = {}

    @classmethod
    def register(cls, connector_type: ConnectorType):
        """Decorator to register a connector implementation.

        Args:
            connector_type: Type identifier for this connector

        Returns:
            Decorator function
        """
        def decorator(connector_class: type[IngestionPort]):
            cls._registry[connector_type] = connector_class
            logger.debug(
                "Registered connector",
                type=connector_type.value,
                class_name=connector_class.__name__,
            )
            return connector_class
        return decorator

    @classmethod
    def create(
        cls,
        connector_type: ConnectorType,
        config: dict[str, Any],
        circuit_breaker: CircuitBreaker | None = None,
        retry_policy: RetryPolicy | None = None,
        rate_limiter: RateLimiter | None = None,
        metrics: MetricsPort | None = None,
    ) -> IngestionPort:
        """Create a connector instance.

        Args:
            connector_type: Type of connector to create
            config: Configuration dictionary for the connector
            circuit_breaker: Optional circuit breaker
            retry_policy: Optional retry policy
            rate_limiter: Optional rate limiter
            metrics: Optional metrics port

        Returns:
            Configured connector instance

        Raises:
            ValueError: If connector type is not registered
        """
        if connector_type not in cls._registry:
            raise ValueError(f"Unknown connector type: {connector_type}")

        connector_class = cls._registry[connector_type]

        # Build kwargs from config and optional dependencies
        kwargs = dict(config)
        if circuit_breaker:
            kwargs["circuit_breaker"] = circuit_breaker
        if retry_policy:
            kwargs["retry_policy"] = retry_policy
        if rate_limiter and hasattr(connector_class, "__init__"):
            # Only pass if connector accepts it
            kwargs["rate_limiter"] = rate_limiter
        if metrics:
            kwargs["metrics"] = metrics

        return connector_class(**kwargs)

    @classmethod
    def create_from_settings(
        cls,
        settings: "SourceSettings",
        metrics: MetricsPort | None = None,
    ) -> IngestionPort:
        """Create a connector from settings object.

        Args:
            settings: Source settings with enabled flag and configuration
            metrics: Optional metrics port

        Returns:
            Configured connector instance
        """
        # Build circuit breaker if configured
        circuit_breaker = None
        if settings.circuit_breaker_enabled:
            circuit_breaker = CircuitBreaker(
                name=settings.name,
                failure_threshold=settings.circuit_breaker_threshold,
                recovery_timeout_seconds=settings.circuit_breaker_timeout,
            )

        # Build retry policy
        retry_policy = RetryPolicy(
            max_retries=settings.max_retries,
            base_delay=settings.retry_delay,
        )

        return cls.create(
            connector_type=ConnectorType(settings.source_type),
            config=settings.to_connector_config(),
            circuit_breaker=circuit_breaker,
            retry_policy=retry_policy,
            metrics=metrics,
        )

    @classmethod
    def get_registered_types(cls) -> list[ConnectorType]:
        """Get list of registered connector types."""
        return list(cls._registry.keys())


# Register default connectors
def _register_default_connectors():
    """Register built-in connector implementations."""
    from ingestion.adapters.connectors import (
        WebSocketConnector,
        SSEConnector,
        PollingConnector,
        WebhookConnector,
        MicroBatchConnector,
        BatchConnector,
    )

    ConnectorFactory._registry[ConnectorType.WEBSOCKET] = WebSocketConnector
    ConnectorFactory._registry[ConnectorType.SSE] = SSEConnector
    ConnectorFactory._registry[ConnectorType.POLLING] = PollingConnector
    ConnectorFactory._registry[ConnectorType.WEBHOOK] = WebhookConnector
    ConnectorFactory._registry[ConnectorType.MICRO_BATCH] = MicroBatchConnector
    ConnectorFactory._registry[ConnectorType.BATCH] = BatchConnector


# Register on import
_register_default_connectors()


class AdapterFactory:
    """Factory for creating data format adapters."""

    _registry: dict[str, type] = {}

    @classmethod
    def register(cls, source_name: str):
        """Register an adapter implementation."""
        def decorator(adapter_class):
            cls._registry[source_name] = adapter_class
            return adapter_class
        return decorator

    @classmethod
    def create(cls, source_name: str) -> "DataAdapter":
        """Create an adapter instance.

        Args:
            source_name: Name of the data source

        Returns:
            Configured adapter instance

        Raises:
            ValueError: If adapter is not registered
        """
        if source_name not in cls._registry:
            raise ValueError(f"Unknown adapter: {source_name}")

        return cls._registry[source_name]()

    @classmethod
    def get_or_default(cls, source_name: str) -> "DataAdapter | None":
        """Get adapter or return None if not found."""
        if source_name in cls._registry:
            return cls._registry[source_name]()
        return None


# Register default adapters
def _register_default_adapters():
    """Register built-in adapter implementations."""
    from ingestion.adapters.formats import (
        FinnhubAdapter,
        DexPaprikaAdapter,
        ENTSOEAdapter,
    )

    AdapterFactory._registry["finnhub"] = FinnhubAdapter
    AdapterFactory._registry["dexpaprika"] = DexPaprikaAdapter
    AdapterFactory._registry["entsoe"] = ENTSOEAdapter


_register_default_adapters()
