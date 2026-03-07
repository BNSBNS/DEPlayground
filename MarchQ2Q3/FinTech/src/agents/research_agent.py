"""Research agent — RAG queries, news, and macro analysis."""

from __future__ import annotations

from src.agents.tools.research_tools import (
    MacroDataInput,
    RAGQueryInput,
    get_macro_data,
    rag_query,
)
from src.logging import get_logger

logger = get_logger(__name__)


def run_research(ticker: str, start: str = "2023-01-01", end: str = "2024-12-31") -> dict:
    """Run the research agent: RAG + macro data gathering.

    Returns a research brief dict with findings from available sources.
    """
    brief: dict = {"ticker": ticker, "rag_results": None, "macro_data": {}}

    # 1. RAG query for company-specific information
    rag_result = rag_query(RAGQueryInput(question=f"Latest earnings and outlook for {ticker}"))
    if rag_result.success:
        brief["rag_results"] = rag_result.data
        logger.info(
            "research_rag_complete",
            ticker=ticker,
            results=rag_result.data.get("num_results", 0),
        )

    # 2. Macro context
    for series_id in ["DGS10", "VIXCLS"]:
        macro_result = get_macro_data(MacroDataInput(series_id=series_id, start=start, end=end))
        if macro_result.success:
            brief["macro_data"][series_id] = macro_result.data

    logger.info("research_complete", ticker=ticker)
    return brief
