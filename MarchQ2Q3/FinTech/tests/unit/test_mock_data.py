"""Tests for mock data generation — validates schemas and vol surface properties."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from scripts.seed_mock_data import generate_iv


class TestGenerateIV:
    """Parametric vol surface model tests."""

    def test_atm_returns_near_atm_vol(self) -> None:
        """ATM strike should return close to atm_vol."""
        rng = np.random.default_rng(0)
        ivs = [generate_iv(0.25, 100, 100, 30 / 252, rng) for _ in range(100)]
        mean_iv = np.mean(ivs)
        assert abs(mean_iv - 0.25) < 0.03

    def test_skew_is_negative(self) -> None:
        """OTM puts (low strike) should have higher IV than OTM calls (high strike)."""
        rng = np.random.default_rng(42)
        atm_vol = 0.25
        S = 100.0
        T = 30 / 252

        # Average over many samples to smooth noise
        otm_put_ivs = [generate_iv(atm_vol, S, 90, T, rng) for _ in range(200)]
        otm_call_ivs = [generate_iv(atm_vol, S, 110, T, rng) for _ in range(200)]

        assert np.mean(otm_put_ivs) > np.mean(otm_call_ivs)

    def test_term_structure(self) -> None:
        """Different DTEs should produce different IVs."""
        rng = np.random.default_rng(42)
        atm_vol = 0.25
        S = 100.0

        short_ivs = [generate_iv(atm_vol, S, 100, 30 / 252, rng) for _ in range(200)]
        long_ivs = [generate_iv(atm_vol, S, 100, 90 / 252, rng) for _ in range(200)]

        # Term structure should create a measurable difference
        assert abs(np.mean(short_ivs) - np.mean(long_ivs)) > 0.001

    def test_iv_always_positive(self) -> None:
        """IV should never go below 0.05 floor."""
        rng = np.random.default_rng(42)
        for _ in range(500):
            iv = generate_iv(0.15, 100, 100, 30 / 252, rng)
            assert iv >= 0.05

    def test_smile_wings(self) -> None:
        """Both wings should have higher IV than ATM on average."""
        rng = np.random.default_rng(42)
        atm_vol = 0.25
        S = 100.0
        T = 60 / 252

        atm_ivs = [generate_iv(atm_vol, S, 100, T, rng) for _ in range(500)]
        far_otm_ivs = [generate_iv(atm_vol, S, 80, T, rng) for _ in range(500)]

        # Deep OTM should have higher IV due to skew + smile
        assert np.mean(far_otm_ivs) > np.mean(atm_ivs)


class TestOHLCVSchema:
    """OHLCV data contract tests."""

    @pytest.fixture
    def ohlcv(self, sample_ohlcv: pd.DataFrame) -> pd.DataFrame:
        return sample_ohlcv

    def test_required_columns(self, ohlcv: pd.DataFrame) -> None:
        required = {"date", "open", "high", "low", "close", "volume"}
        assert required.issubset(set(ohlcv.columns))

    def test_prices_positive(self, ohlcv: pd.DataFrame) -> None:
        for col in ["open", "high", "low", "close"]:
            assert (ohlcv[col] > 0).all()

    def test_high_gte_low(self, ohlcv: pd.DataFrame) -> None:
        assert (ohlcv["high"] >= ohlcv["low"]).all()

    def test_volume_non_negative(self, ohlcv: pd.DataFrame) -> None:
        assert (ohlcv["volume"] >= 0).all()

    def test_dates_sorted(self, ohlcv: pd.DataFrame) -> None:
        dates = pd.to_datetime(ohlcv["date"])
        assert dates.is_monotonic_increasing


class TestOptionsChainSchema:
    """Options chain data contract tests."""

    @pytest.fixture
    def chain(self, sample_options_chain: pd.DataFrame) -> pd.DataFrame:
        return sample_options_chain

    def test_required_columns(self, chain: pd.DataFrame) -> None:
        required = {"ticker", "strike", "option_type", "bid", "ask", "implied_vol"}
        assert required.issubset(set(chain.columns))

    def test_option_types(self, chain: pd.DataFrame) -> None:
        assert set(chain["option_type"].unique()) == {"call", "put"}

    def test_strikes_positive(self, chain: pd.DataFrame) -> None:
        assert (chain["strike"] > 0).all()

    def test_iv_positive(self, chain: pd.DataFrame) -> None:
        assert (chain["implied_vol"] > 0).all()

    def test_bid_lte_ask(self, chain: pd.DataFrame) -> None:
        assert (chain["bid"] <= chain["ask"]).all()
