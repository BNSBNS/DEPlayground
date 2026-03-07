"""Ollama LLM provider (local inference via REST API)."""

from __future__ import annotations

import httpx

from src.llm.base import LLMResponse


class OllamaProvider:
    """LLM provider backed by a local Ollama instance."""

    def __init__(
        self,
        model: str = "llama3",
        base_url: str = "http://localhost:11434",
        timeout: float = 120.0,
    ) -> None:
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

        payload = {
            "model": self._model,
            "messages": all_messages,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": temperature,
            },
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(f"{self._base_url}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()

        content = data.get("message", {}).get("content", "")
        usage: dict[str, int] = {}
        if "prompt_eval_count" in data:
            usage["prompt_tokens"] = data["prompt_eval_count"]
        if "eval_count" in data:
            usage["completion_tokens"] = data["eval_count"]

        return LLMResponse(
            content=content,
            usage=usage,
            model=self._model,
            provider="ollama",
        )
