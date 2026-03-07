"""Scans router — submit and retrieve security scan results."""

from __future__ import annotations

import datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from src.reports.json_report import generate_json_report
from src.reports.sarif import generate_sarif
from src.scanner import run_scan

router = APIRouter(prefix="/api/v1", tags=["scans"])

# In-memory scan store: scan_id → result dict
_scans: dict[str, dict[str, Any]] = {}


class ScanRequest(BaseModel):
    target_url: str
    timeout: float = 10.0


class ScanStatus(BaseModel):
    scan_id: str
    target_url: str
    status: str  # "pending" | "running" | "complete" | "error"
    submitted_at: str
    completed_at: str | None = None
    finding_count: int = 0


@router.post("/scans", status_code=202)
async def submit_scan(
    body: ScanRequest,
    background_tasks: BackgroundTasks,
) -> ScanStatus:
    """Submit a new scan. Returns immediately; scan runs in the background."""
    import uuid  # noqa: PLC0415

    scan_id = str(uuid.uuid4())
    submitted_at = datetime.datetime.now(datetime.UTC).isoformat()
    _scans[scan_id] = {
        "status": "pending",
        "target_url": body.target_url,
        "submitted_at": submitted_at,
        "completed_at": None,
        "result": None,
        "error": None,
    }
    background_tasks.add_task(_run_scan_bg, scan_id, body.target_url, body.timeout)
    return ScanStatus(
        scan_id=scan_id,
        target_url=body.target_url,
        status="pending",
        submitted_at=submitted_at,
    )


@router.get("/scans")
async def list_scans() -> list[ScanStatus]:
    """List all submitted scans."""
    statuses: list[ScanStatus] = []
    for scan_id, entry in _scans.items():
        result = entry.get("result")
        statuses.append(
            ScanStatus(
                scan_id=scan_id,
                target_url=entry["target_url"],
                status=entry["status"],
                submitted_at=entry["submitted_at"],
                completed_at=entry.get("completed_at"),
                finding_count=result.finding_count if result is not None else 0,
            )
        )
    return statuses


@router.get("/scans/{scan_id}")
async def get_scan(scan_id: str) -> dict[str, Any]:
    """Get the full JSON report for a completed scan."""
    entry = _get_or_404(scan_id)
    if entry["status"] != "complete":
        return {"scan_id": scan_id, "status": entry["status"]}
    return generate_json_report(entry["result"])


@router.get("/scans/{scan_id}/sarif")
async def get_scan_sarif(scan_id: str) -> dict[str, Any]:
    """Get the SARIF 2.1.0 report for a completed scan."""
    entry = _get_or_404(scan_id)
    if entry["status"] != "complete":
        raise HTTPException(status_code=409, detail=f"Scan status: {entry['status']}")
    return generate_sarif(entry["result"])


def _get_or_404(scan_id: str) -> dict[str, Any]:
    entry = _scans.get(scan_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Scan {scan_id!r} not found")
    return entry


async def _run_scan_bg(scan_id: str, target_url: str, timeout: float) -> None:
    """Background task: run scan and store result."""
    _scans[scan_id]["status"] = "running"
    try:
        from src.config import ScannerSettings  # noqa: PLC0415

        settings = ScannerSettings(target_url=target_url, request_timeout=timeout)
        result = await run_scan(target_url, settings=settings)
        _scans[scan_id]["status"] = "complete"
        _scans[scan_id]["result"] = result
        _scans[scan_id]["completed_at"] = datetime.datetime.now(datetime.UTC).isoformat()
    except Exception as exc:
        _scans[scan_id]["status"] = "error"
        _scans[scan_id]["error"] = str(exc)
