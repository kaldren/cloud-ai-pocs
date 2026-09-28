from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, HttpUrl
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
    # Number of chunks retrieved from the index and given to the model as sources.
    rag_top_k: Annotated[int, Field(ge=1, le=20)] = 5

    # Tracing (app.telemetry). Unset connection string = tracing off. Ingestion is keyless
    # (Entra ID), so the connection string only says where to send telemetry.
    applicationinsights_connection_string: str | None = None
    # The gen_ai.agent.id on every span; Foundry matches traces to the registered agent by it.
    foundry_agent_name: Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]+$")] = "basic-chatbot"
    # Record prompts and replies on spans. Only for non-sensitive data (the sample handbook).
    genai_capture_content: bool = False
    # Foundry project endpoint; only `app.register_agent` needs it.
    foundry_project_endpoint: HttpUrl | None = None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # pyright: ignore[reportCallIssue]  # required fields come from env / .env
