import os
from pathlib import Path
from dotenv import load_dotenv

# backend/.env is 2 levels up from this file (core/config.py -> app -> backend)
env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)


class Settings:
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "api")
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "https://router.huggingface.co/v1")
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "meta-llama/Llama-3.3-70B-Instruct")
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.1"))
    LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "1024"))
    LLM_TIMEOUT: float = float(os.getenv("LLM_TIMEOUT", "60"))


settings = Settings()
