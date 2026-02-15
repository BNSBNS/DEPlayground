"""Base adapter interface for data format transformation.

Adapters convert external API formats to the internal EnrichedTradeEvent model.
"""

from abc import ABC, abstractmethod
from typing import Any

from src.ingestion.domain.models import EnrichedTradeEvent, SourceMetadata, SourceType


class DataAdapter(ABC):
    """Abstract base class for data format adapters.

    Each adapter handles a specific external API's data format.
    """

    def __init__(
        self,
        source_name: str,
        source_type: SourceType,
        expected_latency_ms: int,
    ):
        """Initialize adapter.

        Args:
            source_name: Name of the data source
            source_type: Type of data source
            expected_latency_ms: Expected latency in milliseconds
        """
        self.source_name = source_name
        self.source_type = source_type
        self.expected_latency_ms = expected_latency_ms

    @abstractmethod
    def transform(self, raw_data: dict[str, Any]) -> list[EnrichedTradeEvent]:
        """Transform raw data to EnrichedTradeEvent(s).

        Args:
            raw_data: Raw event data from the source

        Returns:
            List of EnrichedTradeEvent instances.
            Returns empty list if data cannot be transformed.
        """
        ...

    @abstractmethod
    def can_transform(self, raw_data: dict[str, Any]) -> bool:
        """Check if this adapter can transform the given data.

        Args:
            raw_data: Raw event data

        Returns:
            True if adapter can handle this data format
        """
        ...

    def create_source_metadata(self, batch_id: str | None = None) -> SourceMetadata:
        """Create source metadata for enrichment.

        Args:
            batch_id: Optional batch identifier

        Returns:
            SourceMetadata instance
        """
        from datetime import datetime, UTC

        return SourceMetadata(
            source_type=self.source_type,
            source_name=self.source_name,
            ingestion_timestamp=datetime.now(UTC),
            expected_latency_ms=self.expected_latency_ms,
            batch_id=batch_id,
        )

    def safe_transform(self, raw_data: dict[str, Any]) -> list[EnrichedTradeEvent]:
        """Transform with error handling.

        Args:
            raw_data: Raw event data

        Returns:
            List of events, or empty list on error
        """
        try:
            if self.can_transform(raw_data):
                return self.transform(raw_data)
            return []
        except Exception:
            return []
