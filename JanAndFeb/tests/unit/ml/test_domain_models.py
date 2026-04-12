"""Unit tests for forecast domain models."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.ml.domain.models import (
    AnomalyScore,
    Forecast,
    ForecastBatch,
    ModelMetadata,
)


def _now() -> datetime:
    return datetime(2026, 4, 11, 12, 0, tzinfo=UTC)


def test_forecast_accepts_valid_values() -> None:
    f = Forecast(
        symbol="POWER_DE",
        forecast_for=_now(),
        generated_at=_now(),
        horizon_minutes=15,
        yhat=Decimal("50.12345678"),
        yhat_lower=Decimal("49.00"),
        yhat_upper=Decimal("51.00"),
        model_name="lightgbm",
        model_version="1.0.0",
        feature_hash="abc123",
    )
    assert f.yhat == Decimal("50.12345678")


def test_forecast_coerces_naive_datetime_to_utc() -> None:
    f = Forecast(
        symbol="POWER_DE",
        forecast_for=datetime(2026, 4, 11, 12, 0),
        generated_at=datetime(2026, 4, 11, 12, 0),
        horizon_minutes=15,
        yhat=Decimal("50"),
        model_name="m",
        model_version="v",
        feature_hash="h",
    )
    assert f.forecast_for.tzinfo is not None


def test_forecast_symbol_pattern_enforced() -> None:
    with pytest.raises(ValidationError):
        Forecast(
            symbol="not-valid",
            forecast_for=_now(),
            generated_at=_now(),
            horizon_minutes=15,
            yhat=Decimal("1"),
            model_name="m",
            model_version="v",
            feature_hash="h",
        )


def test_forecast_batch_len_and_iter() -> None:
    forecasts = [
        Forecast(
            symbol="POWER_DE",
            forecast_for=_now(),
            generated_at=_now(),
            horizon_minutes=15,
            yhat=Decimal(str(p)),
            model_name="m",
            model_version="v",
            feature_hash="h",
        )
        for p in (1, 2, 3)
    ]
    batch = ForecastBatch(forecasts=forecasts)
    assert len(batch) == 3
    assert list(batch) == forecasts


def test_anomaly_score_immutable() -> None:
    score = AnomalyScore(
        symbol="POWER_DE",
        window_start=_now(),
        score=0.75,
        is_anomaly=True,
        detector_name="iforest",
    )
    with pytest.raises(ValidationError):
        score.score = 0.1  # type: ignore[misc]


def test_model_metadata_requires_metrics() -> None:
    meta = ModelMetadata(
        model_name="m",
        model_version="v",
        trained_at=_now(),
        metrics={"mae": 0.1, "rmse": 0.2},
        params={"lr": 0.001},
        artifact_uri="/tmp/m/v",
    )
    assert meta.metrics["mae"] == 0.1
