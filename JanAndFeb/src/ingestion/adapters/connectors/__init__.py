"""Driving adapters - data source connectors.

Each connector implements the IngestionPort interface and handles
communication with a specific type of data source.
"""

from src.ingestion.adapters.connectors.base import BaseConnector
from src.ingestion.adapters.connectors.websocket import WebSocketConnector
from src.ingestion.adapters.connectors.sse import SSEConnector
from src.ingestion.adapters.connectors.polling import PollingConnector
from src.ingestion.adapters.connectors.webhook import WebhookConnector
from src.ingestion.adapters.connectors.micro_batch import MicroBatchConnector
from src.ingestion.adapters.connectors.batch import BatchConnector

__all__ = [
    "BaseConnector",
    "WebSocketConnector",
    "SSEConnector",
    "PollingConnector",
    "WebhookConnector",
    "MicroBatchConnector",
    "BatchConnector",
]
