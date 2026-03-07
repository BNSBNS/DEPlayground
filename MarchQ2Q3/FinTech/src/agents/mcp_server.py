"""MCP server — exposes agent tools via stdio transport."""

from __future__ import annotations

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from src.agents.tools.market_tools import (
    MarketDataInput,
    OptionsChainInput,
    get_market_data,
    get_options_chain,
    get_technical_indicators,
)
from src.agents.tools.quant_tools import (
    ImpliedVolInput,
    PriceOptionInput,
    compute_implied_vol,
    price_option,
)
from src.agents.tools.research_tools import (
    MacroDataInput,
    RAGQueryInput,
    get_macro_data,
    rag_query,
)
from src.logging import get_logger

logger = get_logger(__name__)
app = Server("fintech-mcp")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="get_market_data",
            description="Fetch OHLCV market data for a ticker",
            inputSchema=MarketDataInput.model_json_schema(),
        ),
        Tool(
            name="get_options_chain",
            description="Fetch options chain for a ticker",
            inputSchema=OptionsChainInput.model_json_schema(),
        ),
        Tool(
            name="get_technical_indicators",
            description="Compute technical indicators (SMA, RSI, vol) for a ticker",
            inputSchema=MarketDataInput.model_json_schema(),
        ),
        Tool(
            name="price_option",
            description="Price an option with Black-Scholes and compute greeks",
            inputSchema=PriceOptionInput.model_json_schema(),
        ),
        Tool(
            name="compute_implied_vol",
            description="Compute implied volatility from market price",
            inputSchema=ImpliedVolInput.model_json_schema(),
        ),
        Tool(
            name="rag_query",
            description="Query financial documents via RAG",
            inputSchema=RAGQueryInput.model_json_schema(),
        ),
        Tool(
            name="get_macro_data",
            description="Fetch macro data series (FRED)",
            inputSchema=MacroDataInput.model_json_schema(),
        ),
    ]


_TOOL_DISPATCH = {
    "get_market_data": (MarketDataInput, get_market_data),
    "get_options_chain": (OptionsChainInput, get_options_chain),
    "get_technical_indicators": (MarketDataInput, get_technical_indicators),
    "price_option": (PriceOptionInput, price_option),
    "compute_implied_vol": (ImpliedVolInput, compute_implied_vol),
    "rag_query": (RAGQueryInput, rag_query),
    "get_macro_data": (MacroDataInput, get_macro_data),
}


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Dispatch a tool call."""
    if name not in _TOOL_DISPATCH:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]

    input_cls, handler = _TOOL_DISPATCH[name]
    inp = input_cls(**arguments)
    result = handler(inp)
    logger.info("mcp_tool_call", tool=name, success=result.success)

    import json  # noqa: PLC0415

    return [TextContent(type="text", text=json.dumps(result.model_dump(), default=str))]


async def main() -> None:
    """Run the MCP server on stdio."""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
