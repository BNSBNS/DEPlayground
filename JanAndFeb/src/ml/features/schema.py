"""Typed container for feature data.

A ``FeatureFrame`` is a thin wrapper around a pandas DataFrame that carries
the list of feature column names and a deterministic hash of the feature set.
The hash is written to every forecast as ``feature_hash`` so two predictions
made with different feature definitions can never be mistaken for each other.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd

#: Name of the column holding the prediction target.
TARGET_COLUMN = "vwap"


@dataclass(frozen=True)
class FeatureFrame:
    """A DataFrame plus the list of feature columns used for training.

    The ``target`` column is expected to already be present in ``data``.
    Callers use ``feature_columns`` to select the X matrix and ``target``
    to select the y vector.
    """

    data: pd.DataFrame
    feature_columns: tuple[str, ...]
    target: str = TARGET_COLUMN
    feature_hash: str = field(init=False)

    def __post_init__(self) -> None:
        # Deterministic hash over the sorted feature names — stable across runs.
        digest = hashlib.sha256(",".join(sorted(self.feature_columns)).encode("utf-8")).hexdigest()
        object.__setattr__(self, "feature_hash", digest)

    @property
    def x(self) -> pd.DataFrame:
        """Feature matrix (DataFrame with only feature columns)."""
        return self.data[list(self.feature_columns)]

    @property
    def y(self) -> pd.Series[float]:
        """Target vector."""
        return self.data[self.target].astype(float)

    def __len__(self) -> int:
        return len(self.data)
