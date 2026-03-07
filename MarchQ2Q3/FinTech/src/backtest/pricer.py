"""BS repricing wrapper for the backtest engine.

Delegates to src.models.options_pricer for actual calculations.
Adds IV noise to break BS-on-BS circularity during mark-to-market.
"""

from __future__ import annotations

import numpy as np

from src.models.options_pricer import bs_price
from src.models.options_pricer import delta as bs_delta


def reprice_leg(
    spot: float,
    strike: float,
    dte_years: float,
    r: float,
    sigma: float,
    option_type: str,
    q: float = 0.0,
    add_noise: bool = True,
    rng: np.random.Generator | None = None,
) -> tuple[float, float]:
    """Reprice a single leg, returning (price, delta).

    When add_noise=True, adds small IV noise to simulate market
    IV uncertainty and break BS-on-BS circularity.
    """
    if rng is None:
        rng = np.random.default_rng()

    sigma_reprice = sigma
    if add_noise:
        sigma_reprice = max(0.01, sigma + rng.normal(0, 0.01))

    price = bs_price(spot, strike, dte_years, r, sigma_reprice, option_type, q)
    d = bs_delta(spot, strike, dte_years, r, sigma_reprice, option_type, q)
    return price, d
