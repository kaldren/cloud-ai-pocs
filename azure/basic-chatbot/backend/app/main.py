import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from functools import lru_cache, partial
from typing import Annotated

from azure.core.exceptions import AzureError
from azure.search.documents import SearchClient
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from openai import OpenAI, OpenAIError
from opentelemetry import trace

from app.azure_clients import build_openai_client, build_search_client, get_credential
from app.chat import ChatRequest, iter_text, start_stream
from app.config import Settings, get_settings
from app.rag.prompt import build_messages, sources_footer
from app.rag.retrieve import RetrievalError, RetrievedChunk, embed_query, retrieve
from app.telemetry import (
    configure_telemetry,
    end_agent_span_with_error,
    instrument_app,
    start_agent_span,
    traced_reply,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
    configure_telemetry(get_settings(), get_credential())
    yield


app = FastAPI(title="basic-chatbot", lifespan=lifespan)
instrument_app(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@lru_cache(maxsize=1)
def get_openai_client() -> OpenAI:
    """Keyless OpenAI client, built on first use (never at import time)."""
    return build_openai_client(get_settings(), get_credential())


@lru_cache(maxsize=1)
def get_search_client() -> SearchClient:
    """Keyless Search client for the configured index, built on first use."""
    return build_search_client(get_settings(), get_credential())


def retrieve_sources(
    request: ChatRequest, settings: Settings, search_client: SearchClient, client: OpenAI
) -> list[RetrievedChunk]:
    """Retrieve before streaming, so a Search or embedding failure is a 502, not a cut-off reply."""
    embed = partial(embed_query, client, settings.azure_openai_embedding_deployment)
    try:
        return retrieve(search_client, embed, request, settings.rag_top_k)
    except (AzureError, OpenAIError, RetrievalError) as exc:
        # AzureError includes HttpResponseError from Search and credential failures.
        logger.exception("Retrieval failed before streaming")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="Upstream search error"
        ) from exc


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/chat", response_class=StreamingResponse)
def chat(
    request: ChatRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    client: Annotated[OpenAI, Depends(get_openai_client)],
    search_client: Annotated[SearchClient, Depends(get_search_client)],
) -> StreamingResponse:
    """Stream a reply grounded in the index as plain text, ending with the cited sources."""
    # One span for the whole turn. It is active while we retrieve and open the stream, so
    # those spans nest under it, and it ends in traced_reply once the last byte is sent.
    agent_span = start_agent_span(settings, request.messages)
    try:
        with trace.use_span(agent_span, end_on_exit=False):
            sources = retrieve_sources(request, settings, search_client, client)
            messages = build_messages(request, sources)
            try:
                stream = start_stream(client, settings.azure_openai_chat_deployment, messages)
            except (OpenAIError, AzureError) as exc:
                # AzureError covers token acquisition failures from DefaultAzureCredential.
                logger.exception("Upstream model error before streaming")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY, detail="Upstream model error"
                ) from exc
    except Exception as exc:
        end_agent_span_with_error(agent_span, exc)
        raise
    reply = iter_text(stream, on_complete=partial(sources_footer, sources=sources))
    return StreamingResponse(
        traced_reply(reply, agent_span, capture_content=settings.genai_capture_content),
        media_type="text/plain; charset=utf-8",
        # Stop nginx from buffering the stream.
        headers={"X-Accel-Buffering": "no"},
    )
