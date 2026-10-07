from functools import lru_cache

from app.services.llm.base import BaseLLM, LLMError
from app.services.llm.api_llm import APILLM

__all__ = ["BaseLLM", "LLMError", "get_llm", "APILLM"]


@lru_cache(maxsize=1)
def get_llm() -> BaseLLM:
    """Single place that decides which LLM backend is used."""
    return APILLM()
