"""Example ML training using the feature store.

Builds a training dataset via PIT joins, trains a customer churn classifier.
"""
from __future__ import annotations

import asyncio
import random
from datetime import datetime, timedelta

import numpy as np
import structlog

from src.config import get_settings
from src.db.pool import create_pool
from src.logging import setup_logging
from src.serving.training import TrainingDatasetBuilder
from src.storage.offline_store import OfflineStore

logger = structlog.get_logger(__name__)

FEATURE_NAMES = [
    "total_orders",
    "total_spend",
    "avg_order_value",
    "days_since_last_order",
    "order_count_7d",
    "page_views_7d",
    "cart_additions_7d",
    "search_count_7d",
    "session_count_30d",
]


async def build_training_data() -> tuple[np.ndarray, np.ndarray]:
    """Connect to feature store and build a training dataset."""
    setup_logging(json_output=False)
    settings = get_settings()
    pool = await create_pool(settings)

    offline_store = OfflineStore(pool)
    builder = TrainingDatasetBuilder(offline_store)

    # Generate entity keys (customers) with random timestamps
    entity_keys = [f"CUST-{i:04d}" for i in range(1000)]
    timestamps = [
        datetime.utcnow() - timedelta(days=random.randint(1, 30))
        for _ in entity_keys
    ]

    dataset, rows = await builder.build(
        name="churn_training_v1",
        entity_type="customer",
        entity_keys=entity_keys,
        feature_names=FEATURE_NAMES,
        timestamps=timestamps,
    )

    logger.info("training_dataset_built", rows=dataset.row_count, features=len(FEATURE_NAMES))

    # Convert to numpy arrays
    X_list = []
    for row in rows:
        features = []
        for fname in FEATURE_NAMES:
            val = row.get(fname)
            features.append(float(val) if val is not None else 0.0)
        X_list.append(features)

    X = np.array(X_list)

    # Synthetic labels: churn if low activity + high days since last order
    y = np.array([
        1 if (row.get("order_count_7d", 0) or 0) < 2
        and (row.get("days_since_last_order", 0) or 0) > 30
        else 0
        for row in rows
    ])

    await pool.close()
    return X, y


def train_model(X: np.ndarray, y: np.ndarray) -> dict[str, float]:
    """Train a simple sklearn-compatible classifier."""
    # Simple logistic regression using numpy (no sklearn dependency required)
    from scipy.special import expit

    n_samples, n_features = X.shape

    # Normalize features
    mean = X.mean(axis=0)
    std = X.std(axis=0) + 1e-8
    X_norm = (X - mean) / std

    # Add bias
    X_bias = np.column_stack([np.ones(n_samples), X_norm])

    # Gradient descent
    weights = np.zeros(n_features + 1)
    lr = 0.01

    for _ in range(1000):
        logits = X_bias @ weights
        preds = expit(logits)
        gradient = X_bias.T @ (preds - y) / n_samples
        weights -= lr * gradient

    # Evaluate
    final_preds = (expit(X_bias @ weights) > 0.5).astype(int)
    accuracy = (final_preds == y).mean()
    precision = (
        (final_preds & y).sum() / max(final_preds.sum(), 1)
    )
    recall = (
        (final_preds & y).sum() / max(y.sum(), 1)
    )

    metrics = {
        "accuracy": float(accuracy),
        "precision": float(precision),
        "recall": float(recall),
        "total_samples": int(n_samples),
        "positive_rate": float(y.mean()),
    }

    logger.info("model_trained", **metrics)
    return metrics


async def main() -> None:
    setup_logging(json_output=False)
    logger.info("starting_ml_training")

    X, y = await build_training_data()
    metrics = train_model(X, y)

    logger.info("training_complete", metrics=metrics)


if __name__ == "__main__":
    asyncio.run(main())
