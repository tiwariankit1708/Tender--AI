from abc import ABC, abstractmethod
from typing import Optional


class LLMError(Exception):
    """Raised when the LLM service encounters a problem."""
    pass


class BaseLLM(ABC):
    """Contract that every LLM provider must implement."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model identifier (e.g. 'llama-3.3-70b-instruct')."""
        ...

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        json_mode: bool = False,
    ) -> str:
        """Send a prompt and return the model's text reply."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the model can be reached right now."""
        ...
