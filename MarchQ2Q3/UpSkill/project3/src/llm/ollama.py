import json

import httpx
import structlog

log = structlog.get_logger(__name__)


class OllamaProvider:
    """Ollama LLM provider."""

    def __init__(self, base_url: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def generate(self, prompt: str) -> str:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                },
            )
            resp.raise_for_status()
            return resp.json()["response"]

    async def generate_json(self, prompt: str) -> dict:
        raw = await self.generate(prompt + "\nRespond with valid JSON only.")
        # Strip markdown code fences if present
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:-1])
        return json.loads(cleaned)
