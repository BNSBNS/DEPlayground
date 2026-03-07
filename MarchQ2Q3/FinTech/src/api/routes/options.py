"""Options pricing endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from src.agents.tools.quant_tools import PriceOptionInput, price_option
from src.api.schemas import OptionsPriceRequest, OptionsPriceResponse

router = APIRouter(prefix="/api/v1", tags=["options"])


@router.post("/options/price")
def price_option_endpoint(req: OptionsPriceRequest) -> OptionsPriceResponse:
    """Price an option with Black-Scholes and return greeks."""
    result = price_option(
        PriceOptionInput(
            spot=req.spot,
            strike=req.strike,
            time_to_expiry=req.time_to_expiry,
            risk_free_rate=req.risk_free_rate,
            volatility=req.volatility,
            option_type=req.option_type,
            dividend_yield=req.dividend_yield,
        )
    )
    if not result.success or not result.data:
        raise ValueError(result.error or "Pricing failed")

    return OptionsPriceResponse(**result.data)
