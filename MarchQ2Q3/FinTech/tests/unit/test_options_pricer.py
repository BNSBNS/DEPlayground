"""Tests for Black-Scholes option pricer."""

from math import exp

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from src.models.options_pricer import (
    bs_price,
    delta,
    gamma,
    implied_vol,
    rho,
    theta,
    vega,
)


class TestBSPrice:
    """Black-Scholes pricing tests."""

    def test_call_price_positive(self) -> None:
        price = bs_price(100, 100, 1.0, 0.05, 0.20, "call")
        assert price > 0

    def test_put_price_positive(self) -> None:
        price = bs_price(100, 100, 1.0, 0.05, 0.20, "put")
        assert price > 0

    def test_deep_itm_call(self) -> None:
        price = bs_price(200, 100, 1.0, 0.05, 0.20, "call")
        assert price > 95  # at least intrinsic

    def test_deep_otm_call(self) -> None:
        price = bs_price(50, 100, 1.0, 0.05, 0.20, "call")
        assert price < 1

    def test_zero_time(self) -> None:
        assert bs_price(110, 100, 0, 0.05, 0.20, "call") == pytest.approx(10.0)
        assert bs_price(90, 100, 0, 0.05, 0.20, "put") == pytest.approx(10.0)
        assert bs_price(110, 100, 0, 0.05, 0.20, "put") == 0.0

    def test_zero_spot(self) -> None:
        assert bs_price(0, 100, 1.0, 0.05, 0.20, "call") == 0.0

    def test_zero_vol(self) -> None:
        """With zero vol, option is deterministic."""
        price = bs_price(100, 95, 1.0, 0.05, 0.0, "call")
        fwd = 100 * exp(0.05)
        expected = (fwd - 95) * exp(-0.05)
        assert price == pytest.approx(expected, abs=1e-8)

    def test_with_dividend(self) -> None:
        """Dividend reduces call price."""
        no_div = bs_price(100, 100, 1.0, 0.05, 0.20, "call", q=0.0)
        with_div = bs_price(100, 100, 1.0, 0.05, 0.20, "call", q=0.02)
        assert with_div < no_div


class TestPutCallParity:
    """Put-call parity: C - P = S*exp(-qT) - K*exp(-rT)."""

    @pytest.mark.parametrize(
        "S,K,T,r,sigma,q",
        [
            (100, 100, 1.0, 0.05, 0.20, 0.0),
            (150, 100, 0.5, 0.03, 0.30, 0.0),
            (80, 120, 2.0, 0.08, 0.15, 0.0),
            (100, 100, 1.0, 0.05, 0.20, 0.02),  # with dividends
            (200, 150, 0.25, 0.04, 0.40, 0.03),
        ],
    )
    def test_put_call_parity(
        self, S: float, K: float, T: float, r: float, sigma: float, q: float
    ) -> None:
        call = bs_price(S, K, T, r, sigma, "call", q)
        put = bs_price(S, K, T, r, sigma, "put", q)
        expected = S * exp(-q * T) - K * exp(-r * T)
        assert call - put == pytest.approx(expected, abs=1e-8)

    @given(
        S=st.floats(min_value=10, max_value=500),
        K=st.floats(min_value=10, max_value=500),
        T=st.floats(min_value=0.01, max_value=5.0),
        r=st.floats(min_value=0.0, max_value=0.15),
        sigma=st.floats(min_value=0.05, max_value=2.0),
        q=st.floats(min_value=0.0, max_value=0.10),
    )
    @settings(max_examples=200)
    def test_put_call_parity_property(
        self, S: float, K: float, T: float, r: float, sigma: float, q: float
    ) -> None:
        """Property test: put-call parity holds for all valid inputs."""
        call = bs_price(S, K, T, r, sigma, "call", q)
        put = bs_price(S, K, T, r, sigma, "put", q)
        expected = S * exp(-q * T) - K * exp(-r * T)
        assert call - put == pytest.approx(expected, abs=1e-6)


class TestGreeks:
    """Greek calculation tests."""

    def test_atm_call_delta(self) -> None:
        """ATM call delta should be approximately 0.5."""
        d = delta(100, 100, 1.0, 0.05, 0.20, "call")
        assert 0.45 < d < 0.75

    def test_atm_put_delta(self) -> None:
        """ATM put delta should be approximately -0.5."""
        d = delta(100, 100, 1.0, 0.05, 0.20, "put")
        assert -0.75 < d < -0.25

    def test_call_delta_range(self) -> None:
        d = delta(100, 100, 1.0, 0.05, 0.20, "call")
        assert 0.0 <= d <= 1.0

    def test_put_delta_range(self) -> None:
        d = delta(100, 100, 1.0, 0.05, 0.20, "put")
        assert -1.0 <= d <= 0.0

    def test_gamma_positive(self) -> None:
        g = gamma(100, 100, 1.0, 0.05, 0.20)
        assert g > 0

    def test_gamma_peaks_atm(self) -> None:
        g_atm = gamma(100, 100, 0.1, 0.05, 0.20)
        g_otm = gamma(100, 130, 0.1, 0.05, 0.20)
        assert g_atm > g_otm

    def test_vega_positive(self) -> None:
        v = vega(100, 100, 1.0, 0.05, 0.20)
        assert v > 0

    def test_theta_call_negative(self) -> None:
        """Most calls have negative theta (time decay)."""
        t = theta(100, 100, 1.0, 0.05, 0.20, "call")
        assert t < 0

    def test_rho_call_positive(self) -> None:
        r_val = rho(100, 100, 1.0, 0.05, 0.20, "call")
        assert r_val > 0

    def test_rho_put_negative(self) -> None:
        r_val = rho(100, 100, 1.0, 0.05, 0.20, "put")
        assert r_val < 0

    def test_greeks_at_expiry(self) -> None:
        """At T=0, gamma/vega/theta/rho should be 0."""
        assert gamma(100, 100, 0, 0.05, 0.20) == 0.0
        assert vega(100, 100, 0, 0.05, 0.20) == 0.0
        assert theta(100, 100, 0, 0.05, 0.20, "call") == 0.0
        assert rho(100, 100, 0, 0.05, 0.20, "call") == 0.0

    def test_delta_at_expiry(self) -> None:
        assert delta(110, 100, 0, 0.05, 0.20, "call") == 1.0
        assert delta(90, 100, 0, 0.05, 0.20, "call") == 0.0
        assert delta(90, 100, 0, 0.05, 0.20, "put") == -1.0


class TestImpliedVol:
    """Implied volatility solver tests."""

    def test_round_trip(self) -> None:
        """price -> implied_vol -> price should match."""
        sigma_in = 0.25
        price = bs_price(100, 100, 1.0, 0.05, sigma_in, "call")
        sigma_out = implied_vol(price, 100, 100, 1.0, 0.05, "call")
        assert sigma_out == pytest.approx(sigma_in, abs=1e-6)

    def test_round_trip_put(self) -> None:
        sigma_in = 0.30
        price = bs_price(100, 105, 0.5, 0.03, sigma_in, "put")
        sigma_out = implied_vol(price, 100, 105, 0.5, 0.03, "put")
        assert sigma_out == pytest.approx(sigma_in, abs=1e-6)

    def test_round_trip_with_dividend(self) -> None:
        sigma_in = 0.20
        price = bs_price(100, 100, 1.0, 0.05, sigma_in, "call", q=0.02)
        sigma_out = implied_vol(price, 100, 100, 1.0, 0.05, "call", q=0.02)
        assert sigma_out == pytest.approx(sigma_in, abs=1e-6)

    def test_deep_otm(self) -> None:
        """Deep OTM options should still converge."""
        sigma_in = 0.20
        price = bs_price(100, 150, 0.5, 0.05, sigma_in, "call")
        sigma_out = implied_vol(price, 100, 150, 0.5, 0.05, "call")
        assert sigma_out == pytest.approx(sigma_in, abs=1e-4)

    def test_high_vol(self) -> None:
        sigma_in = 1.5
        price = bs_price(100, 100, 1.0, 0.05, sigma_in, "call")
        sigma_out = implied_vol(price, 100, 100, 1.0, 0.05, "call")
        assert sigma_out == pytest.approx(sigma_in, abs=1e-4)

    def test_price_below_intrinsic_raises(self) -> None:
        with pytest.raises(ValueError, match="below intrinsic"):
            implied_vol(0.001, 100, 50, 1.0, 0.05, "call")

    def test_zero_time_raises(self) -> None:
        with pytest.raises(ValueError, match="T<=0"):
            implied_vol(5.0, 100, 100, 0.0, 0.05, "call")

    @given(
        sigma_in=st.floats(min_value=0.10, max_value=1.5),
        S=st.floats(min_value=80, max_value=120),
        K=st.floats(min_value=80, max_value=120),
        T=st.floats(min_value=0.1, max_value=2.0),
        r=st.floats(min_value=0.01, max_value=0.08),
    )
    @settings(max_examples=50)
    def test_round_trip_property(
        self, sigma_in: float, S: float, K: float, T: float, r: float
    ) -> None:
        """Property test: IV round-trip works for reasonable inputs."""
        price = bs_price(S, K, T, r, sigma_in, "call")
        v = vega(S, K, T, r, sigma_in)
        # Skip cases where vega is near-zero (deep ITM/OTM) — numerical issues
        if price > 0.10 and v > 0.01:
            sigma_out = implied_vol(price, S, K, T, r, "call")
            assert sigma_out == pytest.approx(sigma_in, abs=1e-3)
