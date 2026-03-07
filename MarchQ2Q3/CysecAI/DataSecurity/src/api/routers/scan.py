"""Scan router — accept a database URL and return a compliance report."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.audit.tde_checker import check_tde
from src.compliance.report_generator import generate_report, render_html
from src.db.sqlite_adapter import SQLiteAdapter
from src.discovery.schema_scanner import scan_schema

router = APIRouter(prefix="/api/v1", tags=["scan"])

_VALID_FRAMEWORKS = {"PDPA", "GDPR", "PCI-DSS"}
_VALID_FORMATS = {"json", "html"}


class ScanRequest(BaseModel):
    db_url: str = "sqlite:///:memory:"
    frameworks: list[str] = ["PDPA", "GDPR", "PCI-DSS"]
    format: str = "json"


@router.post("/scan", status_code=202)
async def scan(body: ScanRequest) -> dict[str, Any]:
    """Scan a database and return a compliance report."""
    for fw in body.frameworks:
        if fw not in _VALID_FRAMEWORKS:
            raise HTTPException(status_code=400, detail=f"Unknown framework: {fw!r}")
    if body.format not in _VALID_FORMATS:
        raise HTTPException(status_code=400, detail=f"Invalid format: {body.format!r}")

    # For security: only accept SQLite URLs in the API (real DB requires proper auth)
    if not body.db_url.startswith("sqlite"):
        raise HTTPException(
            status_code=400,
            detail="Only SQLite URLs accepted via API. Use the CLI for PostgreSQL/MySQL.",
        )

    adapter = SQLiteAdapter(body.db_url)
    tables = scan_schema(adapter)
    encryption = check_tde(adapter)
    report = generate_report(tables, encryption, frameworks=body.frameworks)

    if body.format == "html":
        return {"report_id": report.report_id, "html": render_html(report)}
    return {"report_id": report.report_id, "report": report.to_dict()}


@router.post("/scan/pii", status_code=202)
async def scan_pii(body: ScanRequest) -> dict[str, Any]:
    """Scan schema and return PII discovery results only."""
    if not body.db_url.startswith("sqlite"):
        raise HTTPException(
            status_code=400,
            detail="Only SQLite URLs accepted via API.",
        )

    adapter = SQLiteAdapter(body.db_url)
    tables = scan_schema(adapter)
    pii_tables = [t for t in tables if t.has_pii]

    return {
        "tables_scanned": len(tables),
        "pii_tables": len(pii_tables),
        "pii_columns": [
            {
                "table": c.table_name,
                "column": c.column_name,
                "classification": str(c.classification),
                "pii_types": [str(p) for p in c.pii_types],
                "masking": str(c.masking_strategy),
            }
            for t in pii_tables
            for c in t.pii_columns
        ],
    }
