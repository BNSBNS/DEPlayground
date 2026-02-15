"""DexPaprika SSE API adapter.

Transforms DexPaprika crypto price stream to EnrichedTradeEvent.
DexPaprika provides: DEX token prices via Server-Sent Events.

API Documentation: https://dexpaprika.com/
"""

from datetime import datetime, UTC
from decimal import Decimal
from typing import Any
from uuid import uuid4

from src.ingestion.adapters.formats.base import DataAdapter
from src.ingestion.domain.models import EnrichedTradeEvent
from src.common.models import SourceType, TradeSide


class DexPaprikaAdapter(DataAdapter):
    """Adapter for DexPaprika SSE API format.

    DexPaprika price message format:
    ```json
    {
        "token": "ethereum",
        "symbol": "ETH",
        "chain": "ethereum",
        "price_usd": 2500.50,
        "price_change_24h": 5.2,
        "volume_24h": 15000000000,
        "market_cap": 300000000000,
        "last_updated": "2024-01-29T10:00:00Z"
    }
    ```

    Example:
        ```python
        adapter = DexPaprikaAdapter()
        events = adapter.transform(sse_message)
        ```
    """

    # Map DexPaprika tokens to internal symbols
    TOKEN_MAPPING = {
        "bitcoin": "CRYPTO_BTC",
        "ethereum": "CRYPTO_ETH",
        "solana": "CRYPTO_SOL",
        "cardano": "CRYPTO_ADA",
        "polkadot": "CRYPTO_DOT",
        "avalanche": "CRYPTO_AVAX",
        "chainlink": "CRYPTO_LINK",
        "uniswap": "CRYPTO_UNI",
    }

    def __init__(self):
        super().__init__(
            source_name="dexpaprika",
            source_type=SourceType.SSE,
            expected_latency_ms=300,
        )

    def can_transform(self, raw_data: dict[str, Any]) -> bool:
        """Check if data is a DexPaprika price message."""
        return (
            isinstance(raw_data, dict)
            and ("token" in raw_data or "symbol" in raw_data)
            and "price_usd" in raw_data
        )

    def _map_token(self, token: str, symbol: str) -> str:
        """Map DexPaprika token to internal format."""
        # Try token name first, then symbol
        if token and token.lower() in self.TOKEN_MAPPING:
            return self.TOKEN_MAPPING[token.lower()]
        return f"CRYPTO_{symbol.upper()}" if symbol else f"CRYPTO_{token.upper()}"

    def _parse_timestamp(self, timestamp_str: str | None) -> datetime:
        """Parse DexPaprika timestamp."""
        if timestamp_str:
            try:
                return datetime.fromisoformat(
                    timestamp_str.replace("Z", "+00:00")
                )
            except ValueError:
                pass
        return datetime.now(UTC)

    def transform(self, raw_data: dict[str, Any]) -> list[EnrichedTradeEvent]:
        """Transform DexPaprika price message to EnrichedTradeEvent.

        Note: DexPaprika provides price data, not individual trades.
        We create a synthetic trade event representing the current price.

        Args:
            raw_data: DexPaprika SSE message

        Returns:
            List with single EnrichedTradeEvent or empty list
        """
        if not self.can_transform(raw_data):
            return []

        try:
            token = raw_data.get("token", "")
            symbol = raw_data.get("symbol", "")

            # Skip if no price
            price = raw_data.get("price_usd")
            if price is None or price <= 0:
                return []

            # Use 24h volume as proxy for trade volume
            # This is a synthetic volume since we don't have actual trade data
            volume = raw_data.get("volume_24h", 1)
            if volume and volume > 0:
                # Normalize to reasonable trade size
                volume = min(volume / 1000000, 1000)  # Cap at 1000 units
            else:
                volume = 1

            metadata = self.create_source_metadata()

            event = EnrichedTradeEvent(
                trade_id=uuid4(),
                symbol=self._map_token(token, symbol),
                price=Decimal(str(price)),
                volume=Decimal(str(max(volume, 0.01))),
                side=TradeSide.BUY,  # Price feeds don't have side
                trader_id="DEXPAPRIKA",
                event_timestamp=self._parse_timestamp(
                    raw_data.get("last_updated")
                ),
                source_metadata=metadata,
            )
            event.compute_idempotency_key()

            return [event]

        except (KeyError, ValueError, TypeError):
            return []


class DexPaprikaSwapAdapter(DataAdapter):
    """Adapter for DexPaprika swap/trade events (if available)."""

    def __init__(self):
        super().__init__(
            source_name="dexpaprika",
            source_type=SourceType.SSE,
            expected_latency_ms=300,
        )

    def can_transform(self, raw_data: dict[str, Any]) -> bool:
        """Check if data is a swap event."""
        return (
            isinstance(raw_data, dict)
            and raw_data.get("type") == "swap"
            and "amount_in" in raw_data
        )

    def transform(self, raw_data: dict[str, Any]) -> list[EnrichedTradeEvent]:
        """Transform swap event to EnrichedTradeEvent."""
        if not self.can_transform(raw_data):
            return []

        try:
            metadata = self.create_source_metadata()

            # Determine symbol from token pair
            token_in = raw_data.get("token_in", "UNKNOWN")
            token_out = raw_data.get("token_out", "USD")
            symbol = f"SWAP_{token_in}_{token_out}".upper()

            event = EnrichedTradeEvent(
                trade_id=uuid4(),
                symbol=symbol,
                price=Decimal(str(raw_data.get("price", 0))),
                volume=Decimal(str(raw_data.get("amount_in", 1))),
                side=TradeSide.BUY if raw_data.get("side") != "sell" else TradeSide.SELL,
                trader_id=raw_data.get("wallet", "DEXPAPRIKA"),
                event_timestamp=datetime.now(UTC),
                source_metadata=metadata,
            )
            event.compute_idempotency_key()

            return [event]

        except (KeyError, ValueError, TypeError):
            return []
