"""Keyless Azure clients: every client authenticates with DefaultAzureCredential (Entra ID)."""

from functools import lru_cache

from azure.core.credentials import TokenCredential
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from openai import OpenAI

from app.config import Settings

SEARCH_SCOPE = "https://search.azure.com/.default"
OPENAI_SCOPE = "https://cognitiveservices.azure.com/.default"


@lru_cache(maxsize=1)
def get_credential() -> TokenCredential:
    return DefaultAzureCredential()


def build_search_client(settings: Settings, credential: TokenCredential) -> SearchClient:
    return SearchClient(
        endpoint=str(settings.azure_search_endpoint),
        index_name=settings.azure_search_index,
        credential=credential,
        credential_scopes=[SEARCH_SCOPE],
    )


def build_search_index_client(settings: Settings, credential: TokenCredential) -> SearchIndexClient:
    """Client for creating / updating the index (the backend owns the index, not Terraform)."""
    return SearchIndexClient(
        endpoint=str(settings.azure_search_endpoint),
        credential=credential,
        credential_scopes=[SEARCH_SCOPE],
    )


def openai_base_url(settings: Settings) -> str:
    """The Azure OpenAI v1 endpoint, which needs no api-version."""
    return f"{str(settings.azure_openai_endpoint).rstrip('/')}/openai/v1/"


def build_openai_client(settings: Settings, credential: TokenCredential) -> OpenAI:
    """Plain OpenAI client on the v1 endpoint; the token provider handles refresh."""
    token_provider = get_bearer_token_provider(credential, OPENAI_SCOPE)
    return OpenAI(base_url=openai_base_url(settings), api_key=token_provider)
