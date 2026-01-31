"""Primary port for data ingestion.

This port defines how external data sources interact with the ingestion system.
Each connector type (WebSocket, SSE, Polling, etc.) implements this interface.
"""

from abc import ABC, abstractmethod
from typing import AsyncIterator, Any


class IngestionPort(ABC):
    """Primary port - defines how data enters the system.

    This is the driving side of the hexagonal architecture.
    Implementations include WebSocket, SSE, Polling, Webhook, etc.

    Attributes:
        name: Human-readable name for the connector
        source_type: Type of data source (websocket, sse, polling, etc.)
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Get the connector name."""
        ...

    @property
    @abstractmethod
    def source_type(self) -> str:
        """Get the source type identifier."""
        ...

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if the connector is currently connected."""
        ...

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the data source.

        Raises:
            ConnectionError: If connection cannot be established
            TimeoutError: If connection times out
        """
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Gracefully disconnect from the data source.

        Should handle cleanup of resources and ensure no data loss.
        """
        ...

    @abstractmethod
    async def stream_events(self) -> AsyncIterator[dict[str, Any]]:
        """Stream raw events from the data source.

        Yields:
            Raw event data as dictionaries. The format depends on the
            source but will be normalized by adapters downstream.

        Raises:
            ConnectionError: If connection is lost during streaming
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the connector is healthy.

        Returns:
            True if the connector is operational, False otherwise
        """
        ...


class BatchIngestionPort(IngestionPort):
    """Extended port for batch-oriented data sources.

    Used for sources that naturally produce data in batches
    (file imports, scheduled API calls, micro-batching).
    """

    @abstractmethod
    async def fetch_batch(self) -> list[dict[str, Any]]:
        """Fetch a batch of events.

        Returns:
            List of raw event dictionaries

        Raises:
            ConnectionError: If data cannot be fetched
        """
        ...

    @abstractmethod
    def get_batch_id(self) -> str:
        """Get the current batch identifier.

        Returns:
            Unique identifier for the current batch
        """
        ...
