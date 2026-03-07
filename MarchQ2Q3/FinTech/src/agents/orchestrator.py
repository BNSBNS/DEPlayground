"""LangGraph orchestrator — coordinates research and quant agents."""

from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, StateGraph
from pydantic import BaseModel, ConfigDict

from src.agents.quant_agent import run_quant
from src.agents.research_agent import run_research
from src.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Internal state (TypedDict for LangGraph)
# ---------------------------------------------------------------------------


class AnalysisState(TypedDict):
    query: str
    ticker: str
    start: str
    end: str
    research_brief: dict | None
    quant_report: dict | None
    final_report: dict | None


# ---------------------------------------------------------------------------
# Output models (Pydantic at boundary)
# ---------------------------------------------------------------------------


class ResearchBrief(BaseModel):
    model_config = ConfigDict(extra="allow")
    ticker: str
    rag_results: dict | None = None
    macro_data: dict | None = None


class QuantReport(BaseModel):
    model_config = ConfigDict(extra="allow")
    ticker: str
    market: dict | None = None
    technicals: dict | None = None
    options: dict | None = None


class AnalysisReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ticker: str
    research_brief: ResearchBrief
    quant_report: QuantReport
    recommendation: str
    suggested_strategies: list[str]


# ---------------------------------------------------------------------------
# Graph nodes
# ---------------------------------------------------------------------------


def research_node(state: AnalysisState) -> dict:
    """Run research agent."""
    brief = run_research(state["ticker"], state["start"], state["end"])
    return {"research_brief": brief}


def quant_node(state: AnalysisState) -> dict:
    """Run quant agent."""
    report = run_quant(state["ticker"], state["start"], state["end"])
    return {"quant_report": report}


def synthesize_node(state: AnalysisState) -> dict:
    """Synthesize findings into a final report."""
    research = state.get("research_brief") or {}
    quant = state.get("quant_report") or {}

    # Deterministic synthesis (no LLM call for now)
    market = quant.get("market") or {}
    technicals = quant.get("technicals") or {}
    options = quant.get("options") or {}

    # Simple rule-based recommendation
    rsi = technicals.get("rsi_14") or 50
    period_return = market.get("period_return") or 0
    avg_iv = options.get("avg_implied_vol") or 0.25

    if rsi < 30:
        recommendation = "Oversold — consider bullish strategies"
    elif rsi > 70:
        recommendation = "Overbought — consider bearish strategies or hedges"
    elif avg_iv > 0.40:
        recommendation = "High IV — consider vol-selling strategies"
    elif period_return > 20:
        recommendation = "Strong uptrend — consider covered calls or protective puts"
    else:
        recommendation = "Neutral — consider iron condors or wait for better setup"

    strategies: list[str] = []
    if avg_iv > 0.35:
        strategies.append("Short iron condor")
        strategies.append("Short strangle")
    if rsi < 35:
        strategies.append("Bull put spread")
    if rsi > 65:
        strategies.append("Bear call spread")
    if not strategies:
        strategies.append("Iron condor")
        strategies.append("Calendar spread")

    return {
        "final_report": {
            "ticker": state["ticker"],
            "research_brief": research,
            "quant_report": quant,
            "recommendation": recommendation,
            "suggested_strategies": strategies,
        }
    }


# ---------------------------------------------------------------------------
# Build graph
# ---------------------------------------------------------------------------


def build_graph() -> StateGraph:
    """Build the LangGraph state graph."""
    graph = StateGraph(AnalysisState)
    graph.add_node("research", research_node)
    graph.add_node("quant", quant_node)
    graph.add_node("synthesize", synthesize_node)

    graph.set_entry_point("research")
    graph.add_edge("research", "quant")
    graph.add_edge("quant", "synthesize")
    graph.add_edge("synthesize", END)

    return graph


def run_analysis(
    ticker: str,
    start: str = "2023-01-01",
    end: str = "2024-12-31",
) -> AnalysisReport:
    """Run the full analysis pipeline and return structured report."""
    graph = build_graph()
    app = graph.compile()

    result = app.invoke(
        {
            "query": f"Analyze {ticker}",
            "ticker": ticker,
            "start": start,
            "end": end,
            "research_brief": None,
            "quant_report": None,
            "final_report": None,
        }
    )

    final = result["final_report"]
    return AnalysisReport(
        ticker=final["ticker"],
        research_brief=ResearchBrief(**final["research_brief"]),
        quant_report=QuantReport(**final["quant_report"]),
        recommendation=final["recommendation"],
        suggested_strategies=final["suggested_strategies"],
    )


if __name__ == "__main__":
    import json
    import sys

    from src.logging import configure_logging

    configure_logging()
    ticker = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    report = run_analysis(ticker)
    print(json.dumps(report.model_dump(), indent=2, default=str))
