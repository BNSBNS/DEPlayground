"""Data format adapters - transform external API formats to domain models.

Each adapter handles a specific external API's data format and converts
it to the canonical EnrichedTradeEvent model.
"""

from src.ingestion.adapters.formats.base import DataAdapter
from src.ingestion.adapters.formats.finnhub import FinnhubAdapter
from src.ingestion.adapters.formats.dexpaprika import DexPaprikaAdapter
from src.ingestion.adapters.formats.entsoe import ENTSOEAdapter

__all__ = [
    "DataAdapter",
    "FinnhubAdapter",
    "DexPaprikaAdapter",
    "ENTSOEAdapter",
]
