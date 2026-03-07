"""Research endpoint — runs the full analysis pipeline."""

from __future__ import annotations

from fastapi import APIRouter

from src.agents.orchestrator import run_analysis
from src.api.schemas import ResearchRequest, ResearchResponse

router = APIRouter(prefix="/api/v1", tags=["research"])


@router.post("/research")
def research(req: ResearchRequest) -> ResearchResponse:
    """Run analysis pipeline for a ticker (sync — offloaded to threadpool)."""
    report = run_analysis(req.ticker, req.start, req.end)
    return ResearchResponse(
        ticker=report.ticker,
        research_brief=report.research_brief.model_dump(),
        quant_report=report.quant_report.model_dump(),
        recommendation=report.recommendation,
        suggested_strategies=report.suggested_strategies,
    )
