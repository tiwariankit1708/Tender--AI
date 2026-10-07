from typing import Optional, Union

import httpx

from app.core.config import settings
from app.services.llm.base import BaseLLM, LLMError


class APILLM(BaseLLM):
    """Talks to any OpenAI-compatible /chat/completions endpoint (HF router, Ollama, vLLM...)."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        default_temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
    ):
        self.base_url = (base_url or settings.llm_base_url).rstrip("/")
        self.api_key = api_key if api_key is not None else settings.llm_api_key
        self._model = model or settings.llm_model
        self.default_temperature = (
            default_temperature
            if default_temperature is not None
            else settings.llm_temperature
        )
        self.max_tokens = (
            max_tokens if max_tokens is not None else settings.llm_max_tokens
        )
        self.timeout = timeout if timeout is not None else settings.llm_timeout

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

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
        if isinstance(messages, str):
            prompt = messages
            messages = None

        if messages is None:
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            if prompt:
                messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self._model,
            "messages": messages,
            "temperature": (
                self.default_temperature if temperature is None else temperature
            ),
            "max_tokens": max_tokens or self.max_tokens,
        }

        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        try:
            response = httpx.post(
                f"{self.base_url}/chat/completions",
                headers=self._headers,
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
        except httpx.ConnectError:
            raise LLMError(
                "Cannot reach the LLM API. Check your internet and LLM_BASE_URL."
            )
        except httpx.TimeoutException:
            raise LLMError("LLM API timed out. Try again.")
        except httpx.HTTPStatusError as e:
            code = e.response.status_code
            if code == 401:
                raise LLMError("Invalid API key (401). Check LLM_API_KEY.")
            if code == 404:
                raise LLMError(
                    f"Model not found (404). Check LLM_MODEL: {self._model}"
                )
            if code == 429:
                raise LLMError("Rate limit hit (429). Wait a minute and retry.")
            raise LLMError(f"LLM API error {code}: {e.response.text}")

        return response.json()["choices"][0]["message"]["content"]

    def is_available(self) -> bool:
        try:
            r = httpx.get(
                f"{self.base_url}/models", headers=self._headers, timeout=10
            )
            return r.status_code == 200
        except Exception:
            return False
