from functools import lru_cache
from pathlib import Path

from pydantic import HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


class Settings(BaseSettings):
    """Backend settings. Auth is Entra ID only (DefaultAzureCredential), so there are no keys."""

    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    azure_search_endpoint: HttpUrl
    azure_search_index: str = "docs"
    azure_openai_endpoint: HttpUrl
    azure_openai_chat_deployment: str
    azure_openai_embedding_deployment: str


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # pyright: ignore[reportCallIssue]  # required fields come from env / .env
