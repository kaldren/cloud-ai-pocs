from unittest.mock import MagicMock, create_autospec, sentinel

import pytest
from azure.core.credentials import TokenCredential

from app import azure_clients
from app.config import Settings


@pytest.fixture
def credential() -> TokenCredential:
    return create_autospec(TokenCredential, instance=True)


def test_get_credential_is_default_azure_credential_and_cached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = MagicMock(return_value=sentinel.credential)
    monkeypatch.setattr(azure_clients, "DefaultAzureCredential", factory)
    azure_clients.get_credential.cache_clear()
    try:
        assert azure_clients.get_credential() is sentinel.credential
        assert azure_clients.get_credential() is sentinel.credential
        factory.assert_called_once_with()
    finally:
        azure_clients.get_credential.cache_clear()


def test_search_client_uses_credential(
    settings: Settings, credential: TokenCredential, monkeypatch: pytest.MonkeyPatch
) -> None:
    sdk = MagicMock()
    monkeypatch.setattr(azure_clients, "SearchClient", sdk)

    client = azure_clients.build_search_client(settings, credential)

    assert client is sdk.return_value
    sdk.assert_called_once_with(
        endpoint="https://srch-test.search.windows.net/",
        index_name="docs",
        credential=credential,
        credential_scopes=["https://search.azure.com/.default"],
    )


def test_search_index_client_uses_credential(
    settings: Settings, credential: TokenCredential, monkeypatch: pytest.MonkeyPatch
) -> None:
    sdk = MagicMock()
    monkeypatch.setattr(azure_clients, "SearchIndexClient", sdk)

    client = azure_clients.build_search_index_client(settings, credential)

    assert client is sdk.return_value
    sdk.assert_called_once_with(
        endpoint="https://srch-test.search.windows.net/",
        credential=credential,
        credential_scopes=["https://search.azure.com/.default"],
    )


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://ais-test.cognitiveservices.azure.com/",
        "https://ais-test.cognitiveservices.azure.com",
    ],
)
def test_openai_base_url_is_v1(
    env: dict[str, str], monkeypatch: pytest.MonkeyPatch, endpoint: str
) -> None:
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", endpoint)

    assert (
        azure_clients.openai_base_url(Settings())  # pyright: ignore[reportCallIssue]
        == "https://ais-test.cognitiveservices.azure.com/openai/v1/"
    )


def test_openai_client_uses_token_provider(
    settings: Settings, credential: TokenCredential, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = MagicMock(return_value=sentinel.token_provider)
    sdk = MagicMock()
    monkeypatch.setattr(azure_clients, "get_bearer_token_provider", provider)
    monkeypatch.setattr(azure_clients, "OpenAI", sdk)

    client = azure_clients.build_openai_client(settings, credential)

    assert client is sdk.return_value
    provider.assert_called_once_with(credential, "https://cognitiveservices.azure.com/.default")
    sdk.assert_called_once_with(
        base_url="https://ais-test.cognitiveservices.azure.com/openai/v1/",
        api_key=sentinel.token_provider,
    )
