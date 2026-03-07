from typing import Protocol


class LLMProvider(Protocol):
    """Protocol for LLM providers."""

    async def generate(self, prompt: str) -> str: ...

    async def generate_json(self, prompt: str) -> dict: ...
