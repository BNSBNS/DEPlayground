"""Transaction data preprocessor.

Converts raw Transaction models to a feature-ready DataFrame with
cleaned, encoded, and transformed columns.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from src.data.generator import Transaction


def transactions_to_dataframe(transactions: list[Transaction]) -> pd.DataFrame:
    """Convert Transaction models to a pandas DataFrame."""
    records = [tx.model_dump() for tx in transactions]
    df = pd.DataFrame(records)
    df["amount"] = df["amount"].astype(float)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df


def handle_missing_values(df: pd.DataFrame) -> pd.DataFrame:
    """Fill missing values: numeric -> median, string -> 'unknown'."""
    df = df.copy()
    for col in df.select_dtypes(include=[np.number]).columns:
        if df[col].isna().any():
            df[col] = df[col].fillna(df[col].median())
    for col in df.select_dtypes(include=["object", "string"]).columns:
        if df[col].isna().any():
            df[col] = df[col].fillna("unknown")
    return df


def encode_categoricals(df: pd.DataFrame) -> pd.DataFrame:
    """Label-encode merchant_category to integer codes."""
    df = df.copy()
    df["merchant_category_code"] = df["merchant_category"].astype("category").cat.codes
    return df


def log_transform_amount(df: pd.DataFrame) -> pd.DataFrame:
    """Add log1p-transformed amount column."""
    df = df.copy()
    df["amount_log"] = np.log1p(df["amount"])
    return df


def preprocess(transactions: list[Transaction]) -> pd.DataFrame:
    """Full preprocessing: convert -> clean -> encode -> transform."""
    df = transactions_to_dataframe(transactions)
    df = handle_missing_values(df)
    df = encode_categoricals(df)
    df = log_transform_amount(df)
    return df
