"""Black-Scholes option pricing with Merton dividend adjustment.

Provides pricing, greeks, and implied volatility for European options.
All formulas use the Merton (1973) dividend-adjusted model:
    S_adj = S * exp(-q * T)
where q is the continuous dividend yield.
"""

from __future__ import annotations

from math import exp, log, sqrt

from scipy.optimize import brentq
from scipy.stats import norm


def _d1(S: float, K: float, T: float, r: float, sigma: float, q: float = 0.0) -> float:
    return (log(S / K) + (r - q + 0.5 * sigma**2) * T) / (sigma * sqrt(T))


def _d2(S: float, K: float, T: float, r: float, sigma: float, q: float = 0.0) -> float:
    return _d1(S, K, T, r, sigma, q) - sigma * sqrt(T)


def bs_price(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    option_type: str,
    q: float = 0.0,
) -> float:
    """Black-Scholes price with Merton dividend adjustment.

    Args:
        S: Spot price
        K: Strike price
        T: Time to expiry (years)
        r: Risk-free rate (annualized)
        sigma: Volatility (annualized)
        option_type: "call" or "put"
        q: Continuous dividend yield (default 0)

    Returns:
        Option price
    """
    if S <= 0:
        return 0.0
    if T <= 0:
        return max(S - K, 0.0) if option_type == "call" else max(K - S, 0.0)
    if sigma <= 0:
        df = exp(-r * T)
        fwd = S * exp((r - q) * T)
        return max(fwd - K, 0.0) * df if option_type == "call" else max(K - fwd, 0.0) * df

    d1 = _d1(S, K, T, r, sigma, q)
    d2 = d1 - sigma * sqrt(T)

    if option_type == "call":
        return S * exp(-q * T) * norm.cdf(d1) - K * exp(-r * T) * norm.cdf(d2)
    return K * exp(-r * T) * norm.cdf(-d2) - S * exp(-q * T) * norm.cdf(-d1)


def delta(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    option_type: str,
    q: float = 0.0,
) -> float:
    """Option delta (dV/dS)."""
    if S <= 0 or T <= 0 or sigma <= 0:
        if T <= 0:
            if option_type == "call":
                return 1.0 if S > K else 0.0
            return -1.0 if S < K else 0.0
        return 0.0

    d1 = _d1(S, K, T, r, sigma, q)
    if option_type == "call":
        return exp(-q * T) * norm.cdf(d1)
    return exp(-q * T) * (norm.cdf(d1) - 1.0)


def gamma(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    q: float = 0.0,
) -> float:
    """Option gamma (d²V/dS²). Same for calls and puts."""
    if S <= 0 or T <= 0 or sigma <= 0:
        return 0.0

    d1 = _d1(S, K, T, r, sigma, q)
    return exp(-q * T) * norm.pdf(d1) / (S * sigma * sqrt(T))


def theta(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    option_type: str,
    q: float = 0.0,
) -> float:
    """Option theta (dV/dT), per year. Divide by 252 for daily."""
    if S <= 0 or T <= 0 or sigma <= 0:
        return 0.0

    d1 = _d1(S, K, T, r, sigma, q)
    d2 = d1 - sigma * sqrt(T)

    common = -(S * exp(-q * T) * norm.pdf(d1) * sigma) / (2 * sqrt(T))
    if option_type == "call":
        return common + q * S * exp(-q * T) * norm.cdf(d1) - r * K * exp(-r * T) * norm.cdf(d2)
    return common - q * S * exp(-q * T) * norm.cdf(-d1) + r * K * exp(-r * T) * norm.cdf(-d2)


def vega(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    q: float = 0.0,
) -> float:
    """Option vega (dV/dsigma). Same for calls and puts. Returns per 1.0 vol change."""
    if S <= 0 or T <= 0 or sigma <= 0:
        return 0.0

    d1 = _d1(S, K, T, r, sigma, q)
    return S * exp(-q * T) * norm.pdf(d1) * sqrt(T)


def rho(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    option_type: str,
    q: float = 0.0,
) -> float:
    """Option rho (dV/dr). Returns per 1.0 rate change."""
    if S <= 0 or T <= 0 or sigma <= 0:
        return 0.0

    d2 = _d2(S, K, T, r, sigma, q)
    if option_type == "call":
        return K * T * exp(-r * T) * norm.cdf(d2)
    return -K * T * exp(-r * T) * norm.cdf(-d2)


def implied_vol(
    market_price: float,
    S: float,
    K: float,
    T: float,
    r: float,
    option_type: str,
    q: float = 0.0,
    tol: float = 1e-8,
    max_iter: int = 100,
) -> float:
    """Implied volatility via Newton-Raphson with Brent fallback.

    Args:
        market_price: Observed market price
        S: Spot price
        K: Strike price
        T: Time to expiry (years)
        r: Risk-free rate
        option_type: "call" or "put"
        q: Continuous dividend yield
        tol: Convergence tolerance
        max_iter: Max Newton iterations

    Returns:
        Implied volatility (annualized)

    Raises:
        ValueError: If no valid IV found (price below intrinsic, etc.)
    """
    if T <= 0 or S <= 0:
        raise ValueError("Cannot compute IV with T<=0 or S<=0")

    # Check intrinsic floor
    intrinsic = (
        max(S * exp(-q * T) - K * exp(-r * T), 0.0)
        if option_type == "call"
        else max(K * exp(-r * T) - S * exp(-q * T), 0.0)
    )
    if market_price < intrinsic - tol:
        raise ValueError(f"Market price {market_price} below intrinsic {intrinsic}")

    # Newton-Raphson
    sigma = 0.3  # initial guess
    for _ in range(max_iter):
        price = bs_price(S, K, T, r, sigma, option_type, q)
        v = vega(S, K, T, r, sigma, q)

        if v < 1e-12:
            break  # vega too small, switch to Brent

        sigma_new = sigma - (price - market_price) / v
        sigma_new = max(0.001, min(sigma_new, 5.0))

        if abs(sigma_new - sigma) < tol:
            return sigma_new
        sigma = sigma_new

    # Brent fallback
    return _brent_iv(market_price, S, K, T, r, option_type, q, tol)


def _brent_iv(
    market_price: float,
    S: float,
    K: float,
    T: float,
    r: float,
    option_type: str,
    q: float,
    tol: float,
) -> float:
    """Brent's method IV solver as fallback."""

    def objective(sigma: float) -> float:
        return bs_price(S, K, T, r, sigma, option_type, q) - market_price

    try:
        return brentq(objective, 0.001, 5.0, xtol=tol)
    except ValueError as e:
        raise ValueError(f"IV solver failed: {e}") from e
