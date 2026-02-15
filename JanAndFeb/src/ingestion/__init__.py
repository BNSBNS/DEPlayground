"""Multi-source data ingestion system.

This module provides a flexible, pattern-based architecture for ingesting data
from multiple sources (WebSocket, SSE, Polling, Webhook, Micro-batch, Batch)
into the energy trading platform.

Architecture:
- Hexagonal Architecture (Ports & Adapters)
- Kappa Architecture (Streaming-First)
- Medallion Architecture (Bronze/Silver/Gold data quality layers)

Design Patterns Used:
- Factory Pattern: Connector creation
- Strategy Pattern: Different ingestion behaviors
- Template Method: Connector lifecycle
- Observer Pattern: Event distribution
- Chain of Responsibility: Processing pipeline
- Adapter Pattern: External API normalization
- Decorator Pattern: Cross-cutting concerns (retry, metrics, circuit breaker)
- Circuit Breaker: Fault tolerance
- Backpressure: Flow control
"""

from src.ingestion.ports import (
    IngestionPort,
    EventPublisherPort,
    MetricsPort,
)

__all__ = [
    "IngestionPort",
    "EventPublisherPort",
    "MetricsPort",
]
