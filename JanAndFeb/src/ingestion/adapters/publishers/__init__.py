"""Driven adapters - event publishers.

Publishers implement the EventPublisherPort interface and handle
sending events to downstream systems.
"""

from src.ingestion.adapters.publishers.kafka_publisher import KafkaPublisher

__all__ = [
    "KafkaPublisher",
]
