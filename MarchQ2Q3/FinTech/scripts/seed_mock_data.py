"""Generate mock data for development and testing.

Creates realistic synthetic financial data:
- OHLCV market data (via yfinance for real historical data)
- FRED macro data (VIX, yields, rates, CPI)
- Synthetic options chains with parametric IV skew
- Synthetic earnings transcripts
- Synthetic news headlines

Usage:
    python -m scripts.seed_mock_data [--force]
"""

from __future__ import annotations

import argparse
from datetime import datetime
from math import log, sqrt
from pathlib import Path

import numpy as np
import pandas as pd

# Tickers and date range
TICKERS = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "JPM", "SPY", "QQQ"]
OPTIONS_TICKERS = ["AAPL", "SPY", "NVDA"]
START_DATE = "2022-01-01"
END_DATE = "2024-12-31"
FRED_SERIES = ["VIXCLS", "DGS10", "DGS2", "FEDFUNDS", "CPIAUCSL"]

DATA_DIR = Path("data/mock")


def generate_iv(atm_vol: float, S: float, K: float, T: float, rng: np.random.Generator) -> float:
    """Generate realistic IV with skew + term structure.

    The model captures three empirical features of vol surfaces:
    1. Skew: OTM puts have higher IV than OTM calls (negative slope)
    2. Smile: Far OTM options on both sides have elevated IV (convexity)
    3. Term structure: Short-dated options have different vol than long-dated

    Args:
        atm_vol: At-the-money implied volatility
        S: Spot price
        K: Strike price
        T: Time to expiry in years
        rng: Random number generator

    Returns:
        Implied volatility for this strike/expiry
    """
    if T <= 0:
        return atm_vol
    moneyness = log(K / S) / (atm_vol * sqrt(T))
    skew = -0.10 * moneyness  # OTM put premium
    smile = 0.02 * moneyness**2  # wing smile
    term = atm_vol * 0.05 * (sqrt(T) - sqrt(30 / 252))  # term structure
    noise = rng.normal(0, 0.005 + 0.01 * abs(moneyness))  # microstructure noise
    return max(atm_vol + skew + smile + term + noise, 0.05)


def seed_ohlcv(force: bool = False) -> None:
    """Download real OHLCV data via yfinance."""
    import yfinance as yf  # noqa: PLC0415

    out_dir = DATA_DIR / "market_data"
    out_dir.mkdir(parents=True, exist_ok=True)

    for ticker in TICKERS:
        path = out_dir / f"{ticker}.parquet"
        if path.exists() and not force:
            print(f"  skip {ticker} (exists)")
            continue

        print(f"  downloading {ticker}...")
        df = yf.download(ticker, start=START_DATE, end=END_DATE, progress=False)
        if df.empty:
            print(f"  WARNING: no data for {ticker}")
            continue

        # Flatten multi-index columns if present
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df = df.reset_index()
        df = df.rename(
            columns={
                "Date": "date",
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Adj Close": "adj_close",
                "Volume": "volume",
            }
        )
        # Use adjusted close as close
        if "adj_close" in df.columns:
            df["close"] = df["adj_close"]
            df = df.drop(columns=["adj_close"])

        df["date"] = pd.to_datetime(df["date"])
        df.to_parquet(path, index=False)
        print(f"  saved {ticker}: {len(df)} rows")


def seed_macro(force: bool = False) -> None:
    """Download real FRED macro data."""
    from fredapi import Fred  # noqa: PLC0415

    from src.config import get_settings  # noqa: PLC0415

    settings = get_settings()
    if not settings.FRED_API_KEY:
        print("  FRED_API_KEY not set, generating synthetic macro data")
        _seed_synthetic_macro(force)
        return

    fred = Fred(api_key=settings.FRED_API_KEY)
    out_dir = DATA_DIR / "macro"
    out_dir.mkdir(parents=True, exist_ok=True)

    for series_id in FRED_SERIES:
        path = out_dir / f"{series_id}.parquet"
        if path.exists() and not force:
            print(f"  skip {series_id} (exists)")
            continue

        print(f"  downloading {series_id}...")
        data = fred.get_series(series_id, observation_start=START_DATE, observation_end=END_DATE)
        df = pd.DataFrame({"date": data.index, "value": data.values})
        df["date"] = pd.to_datetime(df["date"])
        df = df.dropna()
        df.to_parquet(path, index=False)
        print(f"  saved {series_id}: {len(df)} rows")


def _seed_synthetic_macro(force: bool = False) -> None:
    """Generate synthetic macro data when FRED key is not available."""
    out_dir = DATA_DIR / "macro"
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(42)

    dates = pd.bdate_range(START_DATE, END_DATE)

    synthetics = {
        "VIXCLS": (20.0, 5.0),  # mean ~20, std ~5
        "DGS10": (3.5, 0.5),
        "DGS2": (4.0, 0.8),
        "FEDFUNDS": (3.0, 1.5),
        "CPIAUCSL": (300.0, 5.0),
    }

    for series_id, (mean, std) in synthetics.items():
        path = out_dir / f"{series_id}.parquet"
        if path.exists() and not force:
            print(f"  skip {series_id} (exists)")
            continue

        # Random walk with mean reversion
        values = np.zeros(len(dates))
        values[0] = mean
        for i in range(1, len(dates)):
            values[i] = values[i - 1] + 0.02 * (mean - values[i - 1]) + rng.normal(0, std * 0.05)

        if series_id == "VIXCLS":
            values = np.clip(values, 10, 80)  # VIX bounds
        elif series_id in ("DGS10", "DGS2", "FEDFUNDS"):
            values = np.clip(values, 0, 10)  # rate bounds

        df = pd.DataFrame({"date": pd.to_datetime(dates), "value": values})
        df.to_parquet(path, index=False)
        print(f"  saved synthetic {series_id}: {len(df)} rows")


def seed_options_chains(force: bool = False) -> None:
    """Generate synthetic options chains with realistic IV surface."""
    out_dir = DATA_DIR / "options_chains"
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(123)

    for ticker in OPTIONS_TICKERS:
        path = out_dir / f"{ticker}.parquet"
        if path.exists() and not force:
            print(f"  skip {ticker} options (exists)")
            continue

        # Load OHLCV for spot prices
        ohlcv_path = DATA_DIR / "market_data" / f"{ticker}.parquet"
        if not ohlcv_path.exists():
            print(f"  WARNING: no OHLCV for {ticker}, skipping options")
            continue

        ohlcv = pd.read_parquet(ohlcv_path)
        # Sample monthly dates for options generation
        ohlcv["date"] = pd.to_datetime(ohlcv["date"])
        monthly = ohlcv.set_index("date").resample("ME").last().dropna().reset_index()

        rows = []
        for _, bar in monthly.iterrows():
            spot = float(bar["close"])
            trade_date = bar["date"]
            # ATM vol estimate from 20-day realized
            atm_vol = 0.25 + rng.normal(0, 0.03)
            atm_vol = max(0.10, min(atm_vol, 0.60))

            # Generate strikes: 0.80x to 1.20x spot, $5 increments
            strike_min = round(spot * 0.80 / 5) * 5
            strike_max = round(spot * 1.20 / 5) * 5
            strikes = np.arange(strike_min, strike_max + 5, 5.0)

            # Generate expirations: 30, 60, 90 DTE
            for dte_days in [30, 60, 90]:
                T = dte_days / 252
                expiry = trade_date + pd.Timedelta(days=dte_days)

                for K in strikes:
                    for opt_type in ["call", "put"]:
                        iv = generate_iv(atm_vol, spot, K, T, rng)

                        # Price via BS
                        from src.models.options_pricer import bs_price  # noqa: PLC0415

                        r = 0.04  # approximate risk-free
                        price = bs_price(spot, K, T, r, iv, opt_type)

                        # Synthetic bid/ask spread
                        spread = max(0.05, price * rng.uniform(0.02, 0.08))
                        bid = max(0.01, price - spread / 2)
                        ask = price + spread / 2

                        rows.append(
                            {
                                "ticker": ticker,
                                "date": trade_date,
                                "expiration": expiry,
                                "dte": dte_days,
                                "strike": K,
                                "option_type": opt_type,
                                "bid": round(bid, 2),
                                "ask": round(ask, 2),
                                "mid": round(price, 2),
                                "implied_vol": round(iv, 4),
                                "volume": max(1, int(rng.exponential(500))),
                                "open_interest": max(10, int(rng.exponential(2000))),
                                "underlying_price": round(spot, 2),
                            }
                        )

        df = pd.DataFrame(rows)
        df.to_parquet(path, index=False)
        print(f"  saved {ticker} options: {len(df)} rows")


def seed_transcripts(force: bool = False) -> None:
    """Generate synthetic earnings transcripts (plain text, no LLM needed)."""
    out_dir = DATA_DIR / "earnings_transcripts"
    out_dir.mkdir(parents=True, exist_ok=True)

    template = """EARNINGS CALL TRANSCRIPT
{ticker} - Q{quarter} {year}
Date: {date}

PREPARED REMARKS:

CEO: Thank you for joining us today. We're pleased to report {performance} results
for Q{quarter} {year}. Revenue came in at ${revenue}B, {rev_change} year-over-year.
{highlight}

CFO: Looking at the numbers in more detail, gross margin was {margin}%, {margin_change}
from the prior quarter. Operating expenses were well-managed at ${opex}B. We generated
${fcf}B in free cash flow during the quarter. {guidance}

Q&A SESSION:

Analyst: Can you discuss the trajectory for the next quarter?
CEO: We remain {outlook} about our positioning. {forward_statement}
"""

    rng = np.random.default_rng(42)
    tickers = OPTIONS_TICKERS[:3]

    for ticker in tickers:
        for year in [2023, 2024]:
            for q in range(1, 5):
                if year == 2024 and q > 2:
                    continue  # don't go past available data

                fname = f"{ticker}_Q{q}_{year}.txt"
                path = out_dir / fname
                if path.exists() and not force:
                    continue

                revenue = round(rng.uniform(20, 120), 1)
                text = template.format(
                    ticker=ticker,
                    quarter=q,
                    year=year,
                    date=datetime(year, q * 3, 15).strftime("%B %d, %Y"),
                    performance=rng.choice(["strong", "solid", "mixed", "record"]),
                    revenue=revenue,
                    rev_change=f"{'up' if rng.random() > 0.3 else 'down'} {rng.integers(2, 25)}%",
                    highlight=rng.choice(
                        [
                            "Our cloud segment saw exceptional growth.",
                            "Consumer demand remained resilient.",
                            "We accelerated our AI investments this quarter.",
                            "International markets showed strength.",
                        ]
                    ),
                    margin=round(rng.uniform(35, 65), 1),
                    margin_change=rng.choice(["up 50bps", "flat", "down 30bps", "up 120bps"]),
                    opex=round(revenue * rng.uniform(0.25, 0.45), 1),
                    fcf=round(revenue * rng.uniform(0.15, 0.35), 1),
                    guidance=rng.choice(
                        [
                            "We are raising full-year guidance.",
                            "We are reaffirming our prior guidance.",
                            "We expect seasonal headwinds in the next quarter.",
                        ]
                    ),
                    outlook=rng.choice(["optimistic", "cautiously optimistic", "confident"]),
                    forward_statement=rng.choice(
                        [
                            "We see significant opportunities in AI infrastructure.",
                            "Our pipeline remains robust across segments.",
                            "We're investing heavily in next-gen products.",
                        ]
                    ),
                )
                path.write_text(text)

    print(f"  saved {len(list(out_dir.iterdir()))} transcripts")


def seed_news(force: bool = False) -> None:
    """Generate synthetic news headlines."""
    out_dir = DATA_DIR / "news"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "headlines.parquet"

    if path.exists() and not force:
        print("  skip headlines (exists)")
        return

    rng = np.random.default_rng(99)
    templates = [
        "{ticker} beats Q{q} earnings estimates, stock rises {pct}%",
        "{ticker} misses revenue expectations for Q{q}",
        "Analysts upgrade {ticker} on strong {driver} growth",
        "{ticker} announces ${amt}B share buyback program",
        "Fed signals {direction} rate path, {ticker} reacts",
        "{ticker} expands into {market} with new acquisition",
        "Short interest in {ticker} rises to {si}%",
        "{ticker} faces regulatory scrutiny over {issue}",
        "Options volume surges in {ticker} ahead of earnings",
        "{ticker} CEO discusses AI strategy at investor day",
    ]

    rows = []
    dates = pd.bdate_range("2023-01-01", "2024-12-31")
    for date in rng.choice(dates, size=100, replace=True):
        ticker = rng.choice(TICKERS)
        template = rng.choice(templates)
        headline = template.format(
            ticker=ticker,
            q=rng.integers(1, 5),
            pct=round(rng.uniform(1, 8), 1),
            driver=rng.choice(["cloud", "AI", "advertising", "enterprise"]),
            amt=rng.integers(5, 50),
            direction=rng.choice(["hawkish", "dovish", "steady"]),
            market=rng.choice(["healthcare", "automotive", "fintech", "gaming"]),
            si=round(rng.uniform(2, 15), 1),
            issue=rng.choice(["pricing", "data privacy", "competition", "market dominance"]),
        )
        sentiment = rng.choice(["positive", "negative", "neutral"], p=[0.4, 0.3, 0.3])
        rows.append(
            {
                "date": pd.Timestamp(date),
                "ticker": ticker,
                "headline": headline,
                "sentiment": sentiment,
                "source": rng.choice(["Reuters", "Bloomberg", "CNBC", "WSJ"]),
            }
        )

    df = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    df.to_parquet(path, index=False)
    print(f"  saved {len(df)} headlines")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed mock data")
    parser.add_argument("--force", action="store_true", help="Regenerate existing files")
    args = parser.parse_args()

    print("Seeding mock data...")
    print("\n[1/5] OHLCV market data")
    seed_ohlcv(args.force)
    print("\n[2/5] Macro data")
    seed_macro(args.force)
    print("\n[3/5] Options chains")
    seed_options_chains(args.force)
    print("\n[4/5] Earnings transcripts")
    seed_transcripts(args.force)
    print("\n[5/5] News headlines")
    seed_news(args.force)
    print("\nDone!")


if __name__ == "__main__":
    main()
