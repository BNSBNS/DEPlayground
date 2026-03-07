"""Pydantic request/response models for the API."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    detail: str
    status_code: int = 500


class HealthResponse(BaseModel):
    status: str
    version: str = "0.1.0"


class ResearchRequest(BaseModel):
    ticker: str
    start: str = "2023-01-01"
    end: str = "2024-12-31"


class ResearchResponse(BaseModel):
    ticker: str
    research_brief: dict
    quant_report: dict
    recommendation: str
    suggested_strategies: list[str]


class OptionsPriceRequest(BaseModel):
    spot: float
    strike: float
    time_to_expiry: float
    risk_free_rate: float = 0.05
    volatility: float = 0.25
    option_type: str = "call"
    dividend_yield: float = 0.0


class OptionsPriceResponse(BaseModel):
    price: float
    delta: float
    gamma: float
    theta: float
    vega: float
    option_type: str


class BacktestRequest(BaseModel):
    ticker: str
    strategy: str = "vol_selling"
    start: str = "2022-01-01"
    end: str = "2024-12-31"
    initial_capital: float = 100_000.0


class BacktestResponse(BaseModel):
    job_id: str
    status_url: str


class BacktestResultResponse(BaseModel):
    job_id: str
    status: str
    result: dict | None = None
