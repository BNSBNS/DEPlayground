"""Streaming Consumer - Consumes trade events and computes windowed aggregations."""

from src.consumer.db_writer import DatabaseWriter
from src.consumer.dlq_handler import DLQHandler
from src.consumer.kafka_consumer import TradeConsumer
from src.consumer.windowed_aggregator import WindowedAggregator

__all__ = [
    "WindowedAggregator",
    "DatabaseWriter",
    "DLQHandler",
    "TradeConsumer",
]
