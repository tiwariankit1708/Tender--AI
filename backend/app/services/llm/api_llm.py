from typing import Optional

import httpx

from app.services.llm.base import BaseLLM, LLMError


class APILLM(BaseLLM):
    """Any OpenAI-compatible hosted API (Groq, Hugging Face, OpenRouter...)."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        default_temperature: float = 0.1,
        max_tokens: int = 1024,
        timeout: float = 60,
    ):
        if not api_key:
            raise LLMError("LLM_API_KEY is empty. Add your key to backend/.env")

        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._model = model
        self.default_temperature = default_temperature
        self.max_tokens = max_tokens
        self.timeout = timeout

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
        prompt: str,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        json_mode: bool = False,
    ) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self._model,
            "messages": messages,
            "temperature": (
                self.default_temperature if temperature is None else temperature
            ),
            "max_tokens": self.max_tokens,
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
