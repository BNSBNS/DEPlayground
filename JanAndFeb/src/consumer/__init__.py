"""Streaming Consumer - Consumes trade events and computes windowed aggregations.

Key reliability features:
1. Safe offset commit coordination (DB write → commit with retry)
2. Window watermark tracking for safe shutdown
3. True Kafka lag metrics (offset-based)
4. Backpressure and flow control
5. Memory guardrails for aggregator state
"""

from src.consumer.backpressure import BackpressureController, FlowState
from src.consumer.db_writer import DatabaseWriter
from src.consumer.dlq_handler import DLQHandler
from src.consumer.kafka_consumer import TradeConsumer
from src.consumer.offset_manager import OffsetManager
from src.consumer.windowed_aggregator import (
    WindowedAggregator,
    WindowFlushResult,
    WindowState,
)

__all__ = [
    # Core consumer
    "TradeConsumer",
    # Aggregation
    "WindowedAggregator",
    "WindowFlushResult",
    "WindowState",
    # Database
    "DatabaseWriter",
    # Error handling
    "DLQHandler",
    # Reliability
    "OffsetManager",
    "BackpressureController",
    "FlowState",
]
