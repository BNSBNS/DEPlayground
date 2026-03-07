"""Feature engineering pipeline.

Chains preprocessing and all feature extraction steps into a single pipeline.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.data.preprocessor import preprocess
from src.features.behavioral import compute_behavioral_features
from src.features.network import compute_network_features
from src.features.transaction import compute_transaction_features

if TYPE_CHECKING:
    import pandas as pd

    from src.data.generator import Transaction

FEATURE_COLUMNS = [
    # Preprocessor
    "amount_log",
    "merchant_category_code",
    # Transaction-level
    "amount_zscore",
    "is_round_amount",
    "hour_of_day",
    "day_of_week",
    "is_weekend",
    "is_night",
    "merchant_risk_score",
    # Behavioral
    "tx_count_1h",
    "tx_count_24h",
    "avg_amount_7d",
    "amount_deviation",
    "unique_merchants_24h",
    "time_since_last_tx",
    "is_new_category_for_user",
    # Network
    "shared_device_count",
    "unique_ips_24h",
    "is_new_device_for_user",
    "geo_distance_from_home",
]


class FeaturePipeline:
    """Chains preprocessing and feature engineering."""

    def run(self, transactions: list[Transaction]) -> pd.DataFrame:
        """Transform raw transactions into a feature matrix."""
        df = preprocess(transactions)
        df = compute_transaction_features(df)
        df = compute_behavioral_features(df)
        df = compute_network_features(df)
        return df

    @property
    def feature_columns(self) -> list[str]:
        """Names of all engineered feature columns."""
        return list(FEATURE_COLUMNS)
