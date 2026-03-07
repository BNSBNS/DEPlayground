"""Prompt scanner — scores and classifies incoming LLM prompts."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from pydantic import BaseModel

from src.classifier.taxonomy import AttackType

if TYPE_CHECKING:
    from src.classifier.detector import AttackClassifier


class ScanResult(BaseModel):
    """Result of scanning a single prompt."""

    text: str
    attack_type: str
    confidence: float
    blocked: bool
    latency_ms: float


class PromptScanner:
    """Wraps AttackClassifier to produce scan decisions."""

    def __init__(self, classifier: AttackClassifier, block_threshold: float = 0.7) -> None:
        self._classifier = classifier
        self._block_threshold = block_threshold

    @property
    def block_threshold(self) -> float:
        return self._block_threshold

    def scan(self, text: str) -> ScanResult:
        """Score a prompt and decide whether to block it."""
        start = time.perf_counter()
        attack_type, confidence = self._classifier.predict(text)
        latency_ms = (time.perf_counter() - start) * 1000

        blocked = attack_type != AttackType.BENIGN and confidence >= self._block_threshold

        return ScanResult(
            text=text,
            attack_type=attack_type.value,
            confidence=confidence,
            blocked=blocked,
            latency_ms=round(latency_ms, 2),
        )
