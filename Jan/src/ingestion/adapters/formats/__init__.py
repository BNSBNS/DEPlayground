"""Data format adapters - transform external API formats to domain models.

Each adapter handles a specific external API's data format and converts
it to the canonical EnrichedTradeEvent model.
"""

from ingestion.adapters.formats.base import DataAdapter
from ingestion.adapters.formats.finnhub import FinnhubAdapter
from ingestion.adapters.formats.dexpaprika import DexPaprikaAdapter
from ingestion.adapters.formats.entsoe import ENTSOEAdapter

__all__ = [
    "DataAdapter",
    "FinnhubAdapter",
    "DexPaprikaAdapter",
    "ENTSOEAdapter",
]
