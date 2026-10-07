from abc import ABC, abstractmethod
from typing import Optional, Union


class LLMError(Exception):
    """Raised when the LLM service encounters a problem."""
    pass


class BaseLLM(ABC):
    """Every LLM backend implements this contract, so the rest of the app never cares which model is used."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model identifier (e.g. 'llama-3.3-70b-instruct')."""
        ...

    @abstractmethod
    def generate(
        self,
        messages: Union[list[dict], str, None] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        json_mode: bool = False,
        *,
        prompt: Optional[str] = None,
        system: Optional[str] = None,
    ) -> str:
        """Generate response from messages or prompt."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the model can be reached right now."""
        ...
