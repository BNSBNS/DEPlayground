"""OpenAI-compatible LLM provider (httpx, supports any /v1/chat/completions endpoint)."""

from __future__ import annotations

import httpx

from src.llm.base import LLMResponse


class OpenAIProvider:
    """LLM provider for OpenAI (or any compatible) chat completions API."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: str = "https://api.openai.com",
        timeout: float = 120.0,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    async def complete(
        self,
        messages: list[dict[str, str]],
        system: str = "",
        max_tokens: int = 2048,
        temperature: float = 0.1,
    ) -> LLMResponse:
        all_messages = list(messages)
        if system:
            all_messages.insert(0, {"role": "system", "content": system})

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self._model,
            "messages": all_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        url = f"{self._base_url}/v1/chat/completions"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        choice = data.get("choices", [{}])[0]
        content = choice.get("message", {}).get("content", "")

        usage: dict[str, int] = {}
        if raw_usage := data.get("usage"):
            if "prompt_tokens" in raw_usage:
                usage["prompt_tokens"] = raw_usage["prompt_tokens"]
            if "completion_tokens" in raw_usage:
                usage["completion_tokens"] = raw_usage["completion_tokens"]

        return LLMResponse(
            content=content,
            usage=usage,
            model=data.get("model", self._model),
            provider="openai",
        )
