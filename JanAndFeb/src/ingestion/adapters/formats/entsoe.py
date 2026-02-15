"""ENTSO-E Transparency Platform API adapter.

Transforms ENTSO-E European energy market data to EnrichedTradeEvent.
ENTSO-E provides: day-ahead prices, load forecasts, generation data.

API Documentation: https://transparency.entsoe.eu/content/static_content/Static%20content/web%20api/Guide.html
"""

from datetime import datetime, UTC
from decimal import Decimal
from typing import Any
from uuid import uuid4

from src.ingestion.adapters.formats.base import DataAdapter
from src.ingestion.domain.models import EnrichedTradeEvent
from src.common.models import SourceType, TradeSide


class ENTSOEAdapter(DataAdapter):
    """Adapter for ENTSO-E Transparency Platform API format.

    ENTSO-E price response format (simplified):
    ```json
    {
        "TimeSeries": [
            {
                "area": "10Y1001A1001A83F",  # Germany
                "Period": {
                    "timeInterval": {
                        "start": "2024-01-29T00:00Z",
                        "end": "2024-01-30T00:00Z"
                    },
                    "Point": [
                        {"position": 1, "price.amount": 85.50},
                        {"position": 2, "price.amount": 82.30}
                    ]
                }
            }
        ]
    }
    ```

    Example:
        ```python
        adapter = ENTSOEAdapter()
        events = adapter.transform(api_response)
        ```
    """

    # Map ENTSO-E area codes to readable symbols
    AREA_MAPPING = {
        "10Y1001A1001A83F": "POWER_DE",      # Germany
        "10YFR-RTE------C": "POWER_FR",      # France
        "10YNL----------L": "POWER_NL",      # Netherlands
        "10YBE----------2": "POWER_BE",      # Belgium
        "10Y1001A1001A82H": "POWER_AT",      # Austria
        "10YCH-SWISSGRIDZ": "POWER_CH",      # Switzerland
        "10YDK-1--------W": "POWER_DK1",     # Denmark West
        "10YDK-2--------M": "POWER_DK2",     # Denmark East
        "10YNO-1--------2": "POWER_NO1",     # Norway
        "10YSE-1--------K": "POWER_SE1",     # Sweden
        "10YGB----------A": "POWER_GB",      # Great Britain
        "10YES-REE------0": "POWER_ES",      # Spain
        "10YIT-GRTN-----B": "POWER_IT",      # Italy
        "10YPL-AREA-----S": "POWER_PL",      # Poland
    }

    def __init__(self):
        super().__init__(
            source_name="entsoe",
            source_type=SourceType.POLLING,
            expected_latency_ms=900000,  # 15-minute intervals
        )

    def can_transform(self, raw_data: dict[str, Any]) -> bool:
        """Check if data is ENTSO-E format."""
        return (
            isinstance(raw_data, dict)
            and ("TimeSeries" in raw_data or "area" in raw_data or "price" in raw_data)
        )

    def _map_area(self, area_code: str) -> str:
        """Map ENTSO-E area code to internal symbol."""
        return self.AREA_MAPPING.get(area_code, f"POWER_{area_code[:6]}")

    def _parse_timestamp(self, timestamp_str: str) -> datetime:
        """Parse ENTSO-E timestamp format."""
        # Handle various formats
        for fmt in [
            "%Y-%m-%dT%H:%MZ",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M%z",
        ]:
            try:
                dt = datetime.strptime(timestamp_str, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=UTC)
                return dt
            except ValueError:
                continue

        # Fallback: try fromisoformat
        try:
            return datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        except ValueError:
            return datetime.now(UTC)

    def transform(self, raw_data: dict[str, Any]) -> list[EnrichedTradeEvent]:
        """Transform ENTSO-E price data to EnrichedTradeEvent(s).

        Args:
            raw_data: ENTSO-E API response

        Returns:
            List of EnrichedTradeEvent instances
        """
        if not self.can_transform(raw_data):
            return []

        events = []
        metadata = self.create_source_metadata()

        # Handle different response formats
        if "TimeSeries" in raw_data:
            events.extend(self._transform_time_series(raw_data, metadata))
        elif "area" in raw_data and "price" in raw_data:
            events.extend(self._transform_single_price(raw_data, metadata))
        elif isinstance(raw_data.get("prices"), list):
            events.extend(self._transform_price_list(raw_data, metadata))

        return events

    def _transform_time_series(
        self, raw_data: dict[str, Any], metadata
    ) -> list[EnrichedTradeEvent]:
        """Transform ENTSO-E TimeSeries format."""
        events = []

        for series in raw_data.get("TimeSeries", []):
            area = series.get("area", series.get("outBiddingZone_Domain.mRID", "UNKNOWN"))
            symbol = self._map_area(area)

            period = series.get("Period", {})
            start_time = period.get("timeInterval", {}).get("start", "")
            base_time = self._parse_timestamp(start_time) if start_time else datetime.now(UTC)

            for point in period.get("Point", []):
                try:
                    position = int(point.get("position", 1))
                    price = point.get("price.amount", point.get("price", 0))

                    if price is None or float(price) < 0:
                        continue

                    # Calculate timestamp for this point (15-min intervals in Europe)
                    from datetime import timedelta
                    point_time = base_time + timedelta(minutes=(position - 1) * 15)

                    event = EnrichedTradeEvent(
                        trade_id=uuid4(),
                        symbol=symbol,
                        price=Decimal(str(price)),
                        volume=Decimal("1"),  # Price data, not volume
                        side=TradeSide.BUY,
                        trader_id="ENTSOE",
                        event_timestamp=point_time,
                        source_metadata=metadata,
                    )
                    event.compute_idempotency_key()
                    events.append(event)

                except (KeyError, ValueError, TypeError):
                    continue

        return events

    def _transform_single_price(
        self, raw_data: dict[str, Any], metadata
    ) -> list[EnrichedTradeEvent]:
        """Transform single price point."""
        try:
            area = raw_data.get("area", "UNKNOWN")
            price = raw_data.get("price", 0)
            timestamp = raw_data.get("timestamp", raw_data.get("datetime", ""))

            if price is None or float(price) < 0:
                return []

            event = EnrichedTradeEvent(
                trade_id=uuid4(),
                symbol=self._map_area(area),
                price=Decimal(str(price)),
                volume=Decimal("1"),
                side=TradeSide.BUY,
                trader_id="ENTSOE",
                event_timestamp=self._parse_timestamp(timestamp) if timestamp else datetime.now(UTC),
                source_metadata=metadata,
            )
            event.compute_idempotency_key()

            return [event]

        except (KeyError, ValueError, TypeError):
            return []

    def _transform_price_list(
        self, raw_data: dict[str, Any], metadata
    ) -> list[EnrichedTradeEvent]:
        """Transform list of price points."""
        events = []

        for price_point in raw_data.get("prices", []):
            events.extend(self._transform_single_price(price_point, metadata))

        return events


class ENTSOELoadAdapter(DataAdapter):
    """Adapter for ENTSO-E load/demand data."""

    def __init__(self):
        super().__init__(
            source_name="entsoe",
            source_type=SourceType.POLLING,
            expected_latency_ms=900000,
        )

    def can_transform(self, raw_data: dict[str, Any]) -> bool:
        """Check if data is load data."""
        return (
            isinstance(raw_data, dict)
            and "load" in raw_data
        )

    def transform(self, raw_data: dict[str, Any]) -> list[EnrichedTradeEvent]:
        """Transform load data to event."""
        # Load data is tracked differently - this is a placeholder
        return []
