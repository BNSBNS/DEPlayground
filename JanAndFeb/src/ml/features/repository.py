"""SQL repository that reads trade_aggregates into a pandas DataFrame.

Uses the existing psycopg connection pool owned by ``DatabaseWriter`` in
``src.consumer.db_writer`` so the ML layer never opens its own pool and
cannot drift from the trading platform's connection settings.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

from src.common.logging_config import get_logger

if TYPE_CHECKING:
    from datetime import datetime

    from src.consumer.db_writer import DatabaseWriter

logger = get_logger(__name__)

_SELECT_HISTORY_SQL = """
    SELECT
        symbol,
        window_start,
        window_end,
        vwap,
        total_volume,
        trade_count,
        max_price,
        min_price,
        lmp_energy,
        lmp_congestion,
        lmp_loss
    FROM trade_aggregates
    WHERE symbol = %(symbol)s
      AND window_start >= %(start)s
      AND window_start <  %(end)s
    ORDER BY window_start ASC
"""


class SQLFeatureRepository:
    """Reads trade_aggregates rows for a (symbol, time-range) slice.

    Implements the ``FeatureRepository`` Protocol defined in
    ``src.ml.domain.ports``.
    """

    def __init__(self, db_writer: DatabaseWriter) -> None:
        self._db = db_writer

    def load_history(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
    ) -> pd.DataFrame:
        """Load a slice of history as a DataFrame.

        Args:
            symbol: Trading symbol (e.g. "POWER_DE").
            start: Inclusive lower bound of ``window_start`` (UTC).
            end: Exclusive upper bound of ``window_start`` (UTC).

        Returns:
            DataFrame with one row per aggregate window. Returns an empty
            DataFrame (no rows) if no data exists for the range.
        """
        params = {"symbol": symbol, "start": start, "end": end}

        with self._db._get_connection() as conn, conn.cursor() as cur:
            cur.execute(_SELECT_HISTORY_SQL, params)
            rows = cur.fetchall()

        logger.debug(
            "Loaded trade_aggregates history",
            symbol=symbol,
            start=start.isoformat(),
            end=end.isoformat(),
            row_count=len(rows),
        )

        if not rows:
            return pd.DataFrame()

        return pd.DataFrame(rows)
