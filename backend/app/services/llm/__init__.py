from functools import lru_cache

from app.core.config import settings
from app.services.llm.base import BaseLLM, LLMError
from app.services.llm.api_llm import APILLM

__all__ = ["BaseLLM", "LLMError", "get_llm"]


@lru_cache(maxsize=1)
def get_llm() -> BaseLLM:
    """Factory: returns the configured LLM. Swap providers here only."""
    if settings.LLM_PROVIDER == "api":
        return APILLM(
            base_url=settings.LLM_BASE_URL,
            api_key=settings.LLM_API_KEY,
            model=settings.LLM_MODEL,
            default_temperature=settings.LLM_TEMPERATURE,
            max_tokens=settings.LLM_MAX_TOKENS,
            timeout=settings.LLM_TIMEOUT,
        )

    raise ValueError(f"Unknown LLM_PROVIDER: {settings.LLM_PROVIDER}")
