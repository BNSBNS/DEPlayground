from src.config import get_settings
from src.llm.base import LLMProvider
from src.llm.ollama import OllamaProvider

_provider: LLMProvider | None = None


def get_llm_provider() -> LLMProvider:
    """Factory: return the configured LLM provider (singleton)."""
    global _provider
    if _provider is not None:
        return _provider

    settings = get_settings()

    if settings.llm_provider == "ollama":
        _provider = OllamaProvider(
            base_url=settings.llm_base_url,
            model=settings.llm_model,
        )
    else:
        msg = f"Unsupported LLM provider: {settings.llm_provider}"
        raise ValueError(msg)

    return _provider
