"""Anthropic LLM provider (Claude API via httpx)."""

from __future__ import annotations

import httpx

from src.llm.base import LLMResponse

_API_URL = "https://api.anthropic.com/v1/messages"
_API_VERSION = "2023-06-01"


class AnthropicProvider:
    """LLM provider for the Anthropic Messages API."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-20250514",
        timeout: float = 120.0,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout = timeout

    async def complete(
        self,
        messages: list[dict[str, str]],
        system: str = "",
        max_tokens: int = 2048,
        temperature: float = 0.1,
    ) -> LLMResponse:
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": _API_VERSION,
            "content-type": "application/json",
        }

        payload: dict = {
            "model": self._model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system:
            payload["system"] = system

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(_API_URL, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        content = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                content += block.get("text", "")

        usage: dict[str, int] = {}
        if raw_usage := data.get("usage"):
            if "input_tokens" in raw_usage:
                usage["prompt_tokens"] = raw_usage["input_tokens"]
            if "output_tokens" in raw_usage:
                usage["completion_tokens"] = raw_usage["output_tokens"]

        return LLMResponse(
            content=content,
            usage=usage,
            model=data.get("model", self._model),
            provider="anthropic",
        )
