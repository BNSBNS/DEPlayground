"""Shared feature engineering utilities."""

from __future__ import annotations

import numpy as np
import pandas as pd


def rolling_nunique_by_group(
    df: pd.DataFrame,
    group_col: str,
    value_col: str,
    timestamp_col: str,
    window: np.timedelta64,
) -> pd.Series:
    """Count unique values per group within a backward time window.

    For each row, counts distinct values of `value_col` among rows
    in the same group within [timestamp - window, timestamp].
    """
    result = pd.Series(np.zeros(len(df), dtype=np.intp), index=df.index)

    for _, grp in df.groupby(group_col):
        sorted_grp = grp.sort_values(timestamp_col)
        ts = sorted_grp[timestamp_col].values
        vals = sorted_grp[value_col].values
        counts = np.empty(len(sorted_grp), dtype=np.intp)

        for i in range(len(sorted_grp)):
            cutoff = ts[i] - window
            mask = ts[: i + 1] >= cutoff
            counts[i] = len(set(vals[: i + 1][mask]))

        result.loc[sorted_grp.index] = counts

    return result
