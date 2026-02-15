"""Finnhub WebSocket API adapter.

Transforms Finnhub real-time trade data to EnrichedTradeEvent.
Finnhub provides: stock, forex, and crypto trades via WebSocket.

API Documentation: https://finnhub.io/docs/api/websocket-trades
"""

from datetime import datetime, UTC
from decimal import Decimal
from typing import Any
from uuid import uuid4

from src.ingestion.adapters.formats.base import DataAdapter
from src.ingestion.domain.models import EnrichedTradeEvent
from src.common.models import SourceType, TradeSide


class FinnhubAdapter(DataAdapter):
    """Adapter for Finnhub WebSocket API format.

    Finnhub trade message format:
    ```json
    {
        "type": "trade",
        "data": [
            {
                "s": "AAPL",           # Symbol
                "p": 150.25,           # Price
                "v": 100,              # Volume
                "t": 1706800000000,    # Timestamp (ms)
                "c": ["1", "12"]       # Trade conditions
            }
        ]
    }
    ```

    Example:
        ```python
        adapter = FinnhubAdapter()
        events = adapter.transform(websocket_message)
        for event in events:
            publish(event)
        ```
    """

    # Map Finnhub symbols to internal format
    SYMBOL_MAPPING = {
        # Stocks
        "AAPL": "STOCK_AAPL",
        "GOOGL": "STOCK_GOOGL",
        "MSFT": "STOCK_MSFT",
        "AMZN": "STOCK_AMZN",
        "TSLA": "STOCK_TSLA",
        "META": "STOCK_META",
        "NVDA": "STOCK_NVDA",
        # Crypto (Binance)
        "BINANCE:BTCUSDT": "CRYPTO_BTC",
        "BINANCE:ETHUSDT": "CRYPTO_ETH",
        "BINANCE:SOLUSDT": "CRYPTO_SOL",
        # Forex
        "OANDA:EUR_USD": "FOREX_EURUSD",
        "OANDA:GBP_USD": "FOREX_GBPUSD",
    }

    def __init__(self):
        super().__init__(
            source_name="finnhub",
            source_type=SourceType.WEBSOCKET,
            expected_latency_ms=100,
        )

    def can_transform(self, raw_data: dict[str, Any]) -> bool:
        """Check if data is a Finnhub trade message."""
        return (
            isinstance(raw_data, dict)
            and raw_data.get("type") == "trade"
            and "data" in raw_data
            and isinstance(raw_data["data"], list)
        )

    def _map_symbol(self, symbol: str) -> str:
        """Map Finnhub symbol to internal format."""
        return self.SYMBOL_MAPPING.get(symbol, symbol.replace(":", "_").upper())

    def _parse_timestamp(self, timestamp_ms: int | float) -> datetime:
        """Parse Finnhub timestamp (milliseconds since epoch)."""
        return datetime.fromtimestamp(timestamp_ms / 1000, UTC)

    def transform(self, raw_data: dict[str, Any]) -> list[EnrichedTradeEvent]:
        """Transform Finnhub trade message to EnrichedTradeEvent(s).

        Args:
            raw_data: Finnhub WebSocket message

        Returns:
            List of EnrichedTradeEvent instances
        """
        if not self.can_transform(raw_data):
            return []

        events = []
        metadata = self.create_source_metadata()

        for trade in raw_data.get("data", []):
            try:
                event = EnrichedTradeEvent(
                    trade_id=uuid4(),
                    symbol=self._map_symbol(trade["s"]),
                    price=Decimal(str(trade["p"])),
                    volume=Decimal(str(trade["v"])),
                    side=TradeSide.BUY,  # Finnhub doesn't provide trade side
                    trader_id="FINNHUB",
                    event_timestamp=self._parse_timestamp(trade["t"]),
                    source_metadata=metadata,
                )
                event.compute_idempotency_key()
                events.append(event)

            except (KeyError, ValueError, TypeError) as e:
                # Skip malformed trades
                continue

        return events


class FinnhubPingAdapter(DataAdapter):
    """Adapter for Finnhub ping/control messages."""

    def __init__(self):
        super().__init__(
            source_name="finnhub",
            source_type=SourceType.WEBSOCKET,
            expected_latency_ms=100,
        )

    def can_transform(self, raw_data: dict[str, Any]) -> bool:
        """Check if data is a Finnhub control message."""
        msg_type = raw_data.get("type", "")
        return msg_type in ("ping", "subscribe", "unsubscribe", "error")

    def transform(self, raw_data: dict[str, Any]) -> list[EnrichedTradeEvent]:
        """Control messages don't produce trade events."""
        return []
