from collections.abc import Iterator

import pytest

from app.config import Settings, get_settings

ENV = {
    "AZURE_SEARCH_ENDPOINT": "https://srch-test.search.windows.net",
    "AZURE_SEARCH_INDEX": "docs",
    "AZURE_OPENAI_ENDPOINT": "https://ais-test.cognitiveservices.azure.com/",
    "AZURE_OPENAI_CHAT_DEPLOYMENT": "gpt-4.1-mini",
    "AZURE_OPENAI_EMBEDDING_DEPLOYMENT": "text-embedding-3-small",
}


@pytest.fixture(autouse=True)
def no_env_file(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Never read a real backend/.env in tests, and reset the settings cache."""
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    for key in [*ENV, "RAG_TOP_K"]:
        monkeypatch.delenv(key, raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    for key, value in ENV.items():
        monkeypatch.setenv(key, value)
    return ENV


@pytest.fixture
def settings(env: dict[str, str]) -> Settings:
    return get_settings()
