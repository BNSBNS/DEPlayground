"""LLM provider protocol and response model."""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel


class LLMResponse(BaseModel):
    """Standardised response from any LLM provider."""

    content: str
    usage: dict[str, int] = {}
    model: str
    provider: str


class LLMProvider(Protocol):
    """Protocol that all LLM providers must satisfy."""

    async def complete(
        self,
        messages: list[dict[str, str]],
        system: str = "",
        max_tokens: int = 2048,
        temperature: float = 0.1,
    ) -> LLMResponse: ...
