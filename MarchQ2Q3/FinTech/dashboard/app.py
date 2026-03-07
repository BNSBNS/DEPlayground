"""Streamlit dashboard — Research + Options Lab."""

from __future__ import annotations

import requests
import streamlit as st

API_BASE = "http://localhost:8000"
API_KEY = "dev-key"
HEADERS = {"X-API-Key": API_KEY, "Content-Type": "application/json"}

st.set_page_config(page_title="FinTech Intelligence", layout="wide")
page = st.sidebar.selectbox("Page", ["Research", "Options Lab"])


def research_page() -> None:
    st.header("Research Analysis")
    ticker = st.text_input("Ticker", "AAPL")
    if st.button("Analyze"):
        with st.spinner("Running analysis..."):
            resp = requests.post(
                f"{API_BASE}/api/v1/research",
                json={"ticker": ticker},
                headers=HEADERS,
                timeout=120,
            )
        if resp.ok:
            data = resp.json()
            st.subheader("Recommendation")
            st.write(data["recommendation"])
            st.subheader("Suggested Strategies")
            for s in data["suggested_strategies"]:
                st.write(f"- {s}")
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("Research Brief")
                st.json(data["research_brief"])
            with col2:
                st.subheader("Quant Report")
                st.json(data["quant_report"])
        else:
            st.error(f"Error: {resp.status_code} — {resp.text}")


def options_lab_page() -> None:
    st.header("Options Lab — BS Calculator")
    col1, col2 = st.columns(2)
    with col1:
        spot = st.number_input("Spot Price", value=185.0, step=1.0)
        strike = st.number_input("Strike Price", value=185.0, step=1.0)
        tte = st.number_input("Time to Expiry (years)", value=0.0833, step=0.01, format="%.4f")
    with col2:
        vol = st.number_input("Volatility", value=0.25, step=0.01)
        rate = st.number_input("Risk-Free Rate", value=0.05, step=0.01)
        opt_type = st.selectbox("Option Type", ["call", "put"])

    if st.button("Price Option"):
        resp = requests.post(
            f"{API_BASE}/api/v1/options/price",
            json={
                "spot": spot, "strike": strike, "time_to_expiry": tte,
                "risk_free_rate": rate, "volatility": vol, "option_type": opt_type,
            },
            headers=HEADERS,
            timeout=30,
        )
        if resp.ok:
            data = resp.json()
            st.subheader("Results")
            cols = st.columns(5)
            cols[0].metric("Price", f"${data['price']:.4f}")
            cols[1].metric("Delta", f"{data['delta']:.4f}")
            cols[2].metric("Gamma", f"{data['gamma']:.6f}")
            cols[3].metric("Theta", f"{data['theta']:.4f}")
            cols[4].metric("Vega", f"{data['vega']:.4f}")
        else:
            st.error(f"Error: {resp.status_code} — {resp.text}")


if page == "Research":
    research_page()
else:
    options_lab_page()
