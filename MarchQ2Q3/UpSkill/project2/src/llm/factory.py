"""LLM provider factory — instantiate from settings, with singleton access."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.llm.base import LLMProvider

if TYPE_CHECKING:
    from src.config import LLMSettings


def create_llm_provider(settings: LLMSettings) -> LLMProvider:
    """Create an LLM provider based on ``settings.provider``."""
    match settings.provider:
        case "ollama":
            from src.llm.ollama import OllamaProvider

            return OllamaProvider(
                model=settings.model,
                base_url=settings.base_url,
            )
        case "anthropic":
            from src.llm.anthropic import AnthropicProvider

            if not settings.api_key:
                raise ValueError("ANTHROPIC_API_KEY is required for anthropic provider")
            return AnthropicProvider(
                api_key=settings.api_key,
                model=settings.model,
            )
        case "openai":
            from src.llm.openai import OpenAIProvider

            if not settings.api_key:
                raise ValueError("OPENAI_API_KEY is required for openai provider")
            return OpenAIProvider(
                api_key=settings.api_key,
                model=settings.model,
                base_url=settings.base_url,
            )
        case _:
            raise ValueError(f"Unknown LLM provider: {settings.provider!r}")


_provider: LLMProvider | None = None


def get_llm_provider(settings: LLMSettings | None = None) -> LLMProvider:
    """Return a module-level singleton LLM provider.

    On first call, ``settings`` must be provided (or will be loaded from config).
    Subsequent calls return the cached instance.
    """
    global _provider  # noqa: PLW0603
    if _provider is None:
        if settings is None:
            from src.config import get_settings

            settings = get_settings().llm
        _provider = create_llm_provider(settings)
    return _provider
