"""FastAPI application — LLM security firewall API."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Annotated

from fastapi import Body, Depends, FastAPI, HTTPException
from pydantic import BaseModel

from src.classifier.detector import AttackClassifier, train_classifier
from src.config import FirewallSettings
from src.guardrail.scanner import PromptScanner, ScanResult
from src.output_scanner.scanner import OutputScanner, OutputScanResult

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


class _AppState:
    scanner: PromptScanner | None = None
    output_scanner: OutputScanner = OutputScanner()


_state = _AppState()


def _get_scanner() -> PromptScanner:
    if _state.scanner is None:
        raise HTTPException(status_code=503, detail="Scanner not initialised")
    return _state.scanner


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = FirewallSettings()
    if settings.model_dir.exists() and (settings.model_dir / AttackClassifier.MODEL_FILE).exists():
        classifier = AttackClassifier.load(settings.model_dir)
    else:
        classifier, _ = train_classifier(settings.model_dir)
    _state.scanner = PromptScanner(classifier, settings.block_threshold)
    yield
    _state.scanner = None


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="AI/LLM Security Firewall",
    description="Detects and blocks LLM prompt injection, jailbreaks, and data exfiltration",
    version="0.1.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class ScanRequest(BaseModel):
    text: str


class HealthResponse(BaseModel):
    status: str
    threshold: float


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/health", response_model=HealthResponse)
def health(scanner: Annotated[PromptScanner, Depends(_get_scanner)]) -> HealthResponse:
    return HealthResponse(status="ok", threshold=scanner.block_threshold)


@app.post("/api/v1/scan", response_model=ScanResult)
def scan_prompt(
    request: ScanRequest,
    scanner: Annotated[PromptScanner, Depends(_get_scanner)],
) -> ScanResult:
    """Score a prompt and return the guardrail decision."""
    if len(request.text) == 0:
        raise HTTPException(status_code=422, detail="text must not be empty")
    return scanner.scan(request.text)


@app.post("/api/v1/scan/batch", response_model=list[ScanResult])
def scan_batch(
    texts: Annotated[list[str], Body()],
    scanner: Annotated[PromptScanner, Depends(_get_scanner)],
) -> list[ScanResult]:
    """Score a batch of prompts."""
    if not texts:
        raise HTTPException(status_code=422, detail="texts must not be empty")
    return [scanner.scan(t) for t in texts]


@app.post("/api/v1/output/scan", response_model=OutputScanResult)
def scan_output(request: ScanRequest) -> OutputScanResult:
    """Scan an LLM output for PII and system prompt leaks."""
    if len(request.text) == 0:
        raise HTTPException(status_code=422, detail="text must not be empty")
    return _state.output_scanner.scan(request.text)
