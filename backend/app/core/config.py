from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/.env is 2 levels up from this file (core/config.py -> app -> backend)
BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Typed, validated configuration loaded from backend/.env.

    Using pydantic-settings means env vars are parsed and type-checked at
    startup. ``extra="ignore"`` lets unrelated env vars coexist without
    crashing the app.
    """

    llm_provider: str = "api"
    llm_base_url: str = "https://router.huggingface.co/v1"
    llm_api_key: str = ""
    llm_model: str = "meta-llama/Llama-3.3-70B-Instruct"
    llm_temperature: float = 0.1
    llm_max_tokens: int = 2048
    llm_timeout: int = 90

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        extra="ignore",
    )


settings = Settings()
