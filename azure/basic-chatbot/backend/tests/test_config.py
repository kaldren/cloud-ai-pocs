import pytest
from pydantic import ValidationError

from app.config import get_settings


def test_loads_all_keys_from_env(env: dict[str, str]) -> None:
    settings = get_settings()

    assert str(settings.azure_search_endpoint).startswith(env["AZURE_SEARCH_ENDPOINT"])
    assert settings.azure_search_index == "docs"
    assert str(settings.azure_openai_endpoint) == env["AZURE_OPENAI_ENDPOINT"]
    assert settings.azure_openai_chat_deployment == "gpt-4.1-mini"
    assert settings.azure_openai_embedding_deployment == "text-embedding-3-small"


def test_is_cached(env: dict[str, str]) -> None:
    assert get_settings() is get_settings()


def test_index_defaults_to_docs(env: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AZURE_SEARCH_INDEX")

    assert get_settings().azure_search_index == "docs"


def test_has_no_api_key_field(env: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AZURE_SEARCH_API_KEY", "should-be-ignored")

    assert not any("key" in name for name in type(get_settings()).model_fields)


@pytest.mark.parametrize(
    "missing",
    [
        "AZURE_SEARCH_ENDPOINT",
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_CHAT_DEPLOYMENT",
        "AZURE_OPENAI_EMBEDDING_DEPLOYMENT",
    ],
)
def test_required_keys(env: dict[str, str], monkeypatch: pytest.MonkeyPatch, missing: str) -> None:
    monkeypatch.delenv(missing)

    with pytest.raises(ValidationError):
        get_settings()


def test_rejects_non_url_endpoint(env: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AZURE_SEARCH_ENDPOINT", "not-a-url")

    with pytest.raises(ValidationError):
        get_settings()
