"""OpenTelemetry tracing to Application Insights, shown in Foundry as an external agent.

Each /chat request becomes one trace:

    POST /chat                        FastAPI server span
      invoke_agent basic-chatbot      the whole turn, until the last streamed byte
        embeddings ...                query embedding (OpenAI instrumentation)
        POST /indexes/.../search      hybrid search (Azure SDK instrumentation)
        chat gpt-4.1-mini             the streamed completion, with token usage

Every span carries `gen_ai.agent.id`, which Foundry uses to match traces to the agent
registered by `app.register_agent`.
"""

import json
import logging
import os
from collections.abc import Iterator, Sequence

from azure.core.credentials import TokenCredential
from fastapi import FastAPI
from microsoft.opentelemetry import use_microsoft_opentelemetry
from opentelemetry import trace
from opentelemetry.context import Context
from opentelemetry.instrumentation.fastapi import (  # pyright: ignore[reportMissingTypeStubs]
    FastAPIInstrumentor,
)
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import ReadableSpan, Span, SpanProcessor
from opentelemetry.trace import Status, StatusCode

from app.chat import ChatMessage
from app.config import Settings

logger = logging.getLogger(__name__)

SERVICE = "basic-chatbot-api"
# Azure OpenAI in Foundry, per the GenAI semantic conventions.
PROVIDER = "azure.ai.openai"
# Read by the OpenAI instrumentation; "true" records prompts and replies as log events.
CAPTURE_CONTENT_ENV = "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"

# Libraries whose spans only duplicate the Azure SDK and OpenAI spans (or trace the
# telemetry's own metadata lookups). The OpenAI SDK sends through httpx2. FastAPI is
# instrumented per app instead, below.
_DISABLED_INSTRUMENTATIONS = ("fastapi", "requests", "urllib", "urllib3", "httpx", "httpx2")

_tracer = trace.get_tracer(__name__)


class AgentIdSpanProcessor(SpanProcessor):
    """Stamp `gen_ai.agent.id` / `gen_ai.agent.name` on every span this process starts."""

    def __init__(self, agent_name: str) -> None:
        self._agent_name = agent_name

    def on_start(self, span: Span, parent_context: Context | None = None) -> None:
        span.set_attribute("gen_ai.agent.id", self._agent_name)
        span.set_attribute("gen_ai.agent.name", self._agent_name)

    def on_end(self, span: ReadableSpan) -> None:
        pass

    def shutdown(self) -> None:
        pass

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True


def instrument_app(app: FastAPI) -> None:
    """Add the server-span middleware. Cheap and safe before tracing is configured: spans
    stay no-ops until `configure_telemetry` installs the real tracer provider."""
    # exclude_spans: skip the per-message ASGI spans, which would be one per streamed token.
    FastAPIInstrumentor.instrument_app(
        app, excluded_urls="health", exclude_spans=["receive", "send"]
    )


def configure_telemetry(settings: Settings, credential: TokenCredential) -> bool:
    """Export traces, metrics and logs to Application Insights. Returns False when disabled."""
    if not settings.applicationinsights_connection_string:
        logger.info("APPLICATIONINSIGHTS_CONNECTION_STRING is not set; tracing is off")
        return False
    os.environ[CAPTURE_CONTENT_ENV] = str(settings.genai_capture_content).lower()
    use_microsoft_opentelemetry(
        enable_azure_monitor=True,
        azure_monitor_connection_string=settings.applicationinsights_connection_string,
        # Keyless ingestion: the identity needs Monitoring Metrics Publisher on the resource.
        azure_monitor_exporter_credential=credential,
        resource=Resource.create({SERVICE_NAME: SERVICE}),
        span_processors=[AgentIdSpanProcessor(settings.foundry_agent_name)],
        # Keep every trace, whole. The default rate-limited sampler caps spans per second,
        # which drops parts of a chat turn (it has ~10 spans) even at PoC traffic.
        sampling_ratio=1.0,
        instrumentation_options={name: {"enabled": False} for name in _DISABLED_INSTRUMENTATIONS},
    )
    logger.info("Tracing to Application Insights as agent %r", settings.foundry_agent_name)
    return True


def _messages_attribute(role: str, text: str) -> dict[str, object]:
    return {"role": role, "parts": [{"type": "text", "content": text}]}


def start_agent_span(settings: Settings, messages: Sequence[ChatMessage]) -> trace.Span:
    """Start (but don't activate) the `invoke_agent` span for one chat turn."""
    span = _tracer.start_span(f"invoke_agent {settings.foundry_agent_name}")
    span.set_attribute("gen_ai.operation.name", "invoke_agent")
    span.set_attribute("gen_ai.provider.name", PROVIDER)
    span.set_attribute("gen_ai.request.model", settings.azure_openai_chat_deployment)
    if settings.genai_capture_content:
        span.set_attribute(
            "gen_ai.input.messages",
            json.dumps([_messages_attribute(m.role.value, m.content) for m in messages]),
        )
    return span


def end_agent_span_with_error(span: trace.Span, exc: BaseException) -> None:
    span.record_exception(exc)
    span.set_status(Status(StatusCode.ERROR, type(exc).__name__))
    span.end()


def traced_reply(
    chunks: Iterator[str], span: trace.Span, *, capture_content: bool
) -> Iterator[str]:
    """Pass the streamed reply through, then record it and end the span.

    The span is ended here, not in the route handler, because the reply streams after the
    handler returns. It also ends if the client disconnects part-way (GeneratorExit).
    """
    parts: list[str] = []
    try:
        for text in chunks:
            parts.append(text)
            yield text
    finally:
        if capture_content:
            reply = _messages_attribute("assistant", "".join(parts))
            span.set_attribute("gen_ai.output.messages", json.dumps([reply]))
        span.end()
