from collections.abc import Iterator

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app.config import Settings, get_settings
from app.telemetry import AgentIdSpanProcessor

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
    optional = [
        "RAG_TOP_K",
        "APPLICATIONINSIGHTS_CONNECTION_STRING",
        "FOUNDRY_AGENT_NAME",
        "GENAI_CAPTURE_CONTENT",
        "FOUNDRY_PROJECT_ENDPOINT",
    ]
    for key in [*ENV, *optional]:
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


_EXPORTER = InMemorySpanExporter()


@pytest.fixture(scope="session")
def _tracer_provider() -> TracerProvider:
    """The global tracer provider can be set once per process, so tests share one."""
    provider = TracerProvider()
    provider.add_span_processor(AgentIdSpanProcessor("test-agent"))
    provider.add_span_processor(SimpleSpanProcessor(_EXPORTER))
    trace.set_tracer_provider(provider)
    return provider


@pytest.fixture
def spans(_tracer_provider: TracerProvider) -> Iterator[InMemorySpanExporter]:
    """Finished spans recorded during one test."""
    _EXPORTER.clear()
    yield _EXPORTER
    _EXPORTER.clear()
