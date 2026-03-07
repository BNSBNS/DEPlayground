"""Backtest endpoint — async job pattern."""

from __future__ import annotations

import asyncio
from uuid import uuid4

from fastapi import APIRouter

from src.api.schemas import BacktestRequest, BacktestResponse, BacktestResultResponse

router = APIRouter(prefix="/api/v1", tags=["backtest"])

# In-memory job store (replace with Redis/DB in production)
_jobs: dict[str, dict] = {}
# Keep strong references to background tasks to prevent GC cancellation
_background_tasks: set[asyncio.Task] = set()


async def _run_backtest_job(job_id: str, req: BacktestRequest) -> None:
    """Run backtest in background."""
    from datetime import date  # noqa: PLC0415

    from src.backtest.engine import BacktestConfig, run_backtest  # noqa: PLC0415
    from src.backtest.reporting import compute_metrics  # noqa: PLC0415
    from src.backtest.strategies.vol_selling import VolSellingStrategy  # noqa: PLC0415
    from src.data.fetchers import get_fetcher  # noqa: PLC0415

    try:
        _jobs[job_id]["status"] = "running"
        fetcher = get_fetcher()
        ohlcv = fetcher.get_ohlcv(req.ticker, req.start, req.end)

        if req.strategy == "vol_selling":
            strategy = VolSellingStrategy()
        else:
            raise ValueError(f"Unknown strategy: {req.strategy}")

        config = BacktestConfig(
            ticker=req.ticker,
            start=date.fromisoformat(req.start),
            end=date.fromisoformat(req.end),
            initial_capital=req.initial_capital,
        )

        portfolio, ledger = await asyncio.to_thread(run_backtest, strategy, ohlcv, config)
        metrics = compute_metrics(portfolio, ledger)
        _jobs[job_id]["status"] = "completed"
        _jobs[job_id]["result"] = {
            "total_trades": metrics.total_trades,
            "win_rate": metrics.win_rate,
            "sharpe": metrics.sharpe,
            "max_drawdown": metrics.max_drawdown,
            "total_pnl": metrics.total_pnl,
            "cagr": metrics.cagr,
        }
    except Exception as e:
        _jobs[job_id]["status"] = "failed"
        _jobs[job_id]["result"] = {"error": str(e)}


@router.post("/backtest", status_code=202)
async def start_backtest(req: BacktestRequest) -> BacktestResponse:
    """Start an async backtest job."""
    job_id = str(uuid4())[:8]
    _jobs[job_id] = {"status": "pending", "result": None}
    task = asyncio.create_task(_run_backtest_job(job_id, req))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return BacktestResponse(
        job_id=job_id,
        status_url=f"/api/v1/backtest/{job_id}",
    )


@router.get("/backtest/{job_id}")
def get_backtest_result(job_id: str) -> BacktestResultResponse:
    """Poll for backtest job status and results."""
    if job_id not in _jobs:
        return BacktestResultResponse(job_id=job_id, status="not_found")
    job = _jobs[job_id]
    return BacktestResultResponse(
        job_id=job_id,
        status=job["status"],
        result=job["result"],
    )
