"""GJR-GARCH volatility forecast with Student-t innovations."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from arch import arch_model

from src.logging import get_logger

logger = get_logger(__name__)


@dataclass
class VolForecastResult:
    """Result of a GARCH volatility forecast."""

    conditional_vol: np.ndarray  # fitted conditional vol series
    forecast_1d: float  # 1-day ahead annualized vol
    forecast_5d: float  # 5-day ahead annualized vol
    params: dict
    aic: float
    bic: float


def fit_garch(
    returns: np.ndarray,
    p: int = 1,
    o: int = 1,
    q: int = 1,
    dist: str = "t",
    horizon: int = 5,
) -> VolForecastResult:
    """Fit GJR-GARCH(p,o,q) with Student-t distribution.

    Args:
        returns: array of log returns (decimal, not percent)
        p, o, q: GARCH order (o=1 for GJR leverage term)
        dist: distribution ('t' for Student-t, 'normal' for Gaussian)
        horizon: forecast horizon in days

    Returns:
        VolForecastResult with fitted model and forecasts
    """
    # Scale to percentage returns for numerical stability
    returns_pct = returns * 100

    model = arch_model(
        returns_pct,
        vol="GARCH",
        p=p,
        o=o,
        q=q,
        dist=dist,
        mean="Constant",
    )
    result = model.fit(disp="off")

    # Conditional vol (annualized, back to decimal scale)
    cond_vol = result.conditional_volatility / 100 * np.sqrt(252)

    # Forecasts
    forecasts = result.forecast(horizon=horizon)
    # variance is in percentage^2 scale
    var_1d = forecasts.variance.iloc[-1, 0]
    var_5d = forecasts.variance.iloc[-1, :horizon].mean()

    forecast_1d = np.sqrt(var_1d) / 100 * np.sqrt(252)
    forecast_5d = np.sqrt(var_5d) / 100 * np.sqrt(252)

    params = {
        "omega": result.params.get("omega", 0),
        "alpha": result.params.get("alpha[1]", 0),
        "gamma": result.params.get("gamma[1]", 0),
        "beta": result.params.get("beta[1]", 0),
    }
    if dist == "t":
        params["nu"] = result.params.get("nu", 0)

    logger.info(
        "garch_fit",
        aic=f"{result.aic:.1f}",
        bic=f"{result.bic:.1f}",
        forecast_1d=f"{forecast_1d:.4f}",
    )

    return VolForecastResult(
        conditional_vol=cond_vol.values,
        forecast_1d=forecast_1d,
        forecast_5d=forecast_5d,
        params=params,
        aic=result.aic,
        bic=result.bic,
    )
