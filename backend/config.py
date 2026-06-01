"""Application configuration."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent


class Settings(BaseSettings):
    """Typed settings, auto-loaded from environment variables or a .env file."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    llm_provider: str = "ollama"
    llm_model: str = "llama3.2"
    llm_api_key: str = ""

    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_timeout_seconds: float = 120.0

    openai_base_url: str = "https://api.openai.com/v1"
    anthropic_base_url: str = "https://api.anthropic.com"
    anthropic_version: str = "2023-06-01"

    database_url: str = "sqlite:///./data/inbox.db"
    data_dir: str = "data"

    max_llm_retries: int = 2


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_database_path() -> Path:
    """Resolve SQLite file path from database_url (sqlite:///./data/inbox.db)."""
    settings = get_settings()
    url = settings.database_url
    if not url.startswith("sqlite:///"):
        raise ValueError(f"Only sqlite:/// URLs are supported in MVP, got: {url}")
    relative = url.removeprefix("sqlite:///")
    path = Path(relative)
    if not path.is_absolute():
        path = BACKEND_ROOT / path
    return path


def get_data_dir() -> Path:
    settings = get_settings()
    data = Path(settings.data_dir)
    if not data.is_absolute():
        data = BACKEND_ROOT / data
    return data
