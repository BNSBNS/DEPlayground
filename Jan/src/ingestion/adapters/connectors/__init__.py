"""Driving adapters - data source connectors.

Each connector implements the IngestionPort interface and handles
communication with a specific type of data source.
"""

from ingestion.adapters.connectors.base import BaseConnector
from ingestion.adapters.connectors.websocket import WebSocketConnector
from ingestion.adapters.connectors.sse import SSEConnector
from ingestion.adapters.connectors.polling import PollingConnector
from ingestion.adapters.connectors.webhook import WebhookConnector
from ingestion.adapters.connectors.micro_batch import MicroBatchConnector
from ingestion.adapters.connectors.batch import BatchConnector

__all__ = [
    "BaseConnector",
    "WebSocketConnector",
    "SSEConnector",
    "PollingConnector",
    "WebhookConnector",
    "MicroBatchConnector",
    "BatchConnector",
]
