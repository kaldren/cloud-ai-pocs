import logging
from functools import lru_cache
from typing import Annotated

from azure.core.exceptions import AzureError
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from openai import OpenAI, OpenAIError

from app.azure_clients import build_openai_client, get_credential
from app.chat import ChatRequest, iter_text, start_stream
from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

app = FastAPI(title="basic-chatbot")

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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/chat", response_class=StreamingResponse)
def chat(
    request: ChatRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    client: Annotated[OpenAI, Depends(get_openai_client)],
) -> StreamingResponse:
    """Stream the assistant's reply as plain text chunks."""
    try:
        stream = start_stream(client, settings.azure_openai_chat_deployment, request)
    except (OpenAIError, AzureError) as exc:
        # AzureError covers token acquisition failures from DefaultAzureCredential.
        logger.exception("Upstream model error before streaming")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="Upstream model error"
        ) from exc
    return StreamingResponse(
        iter_text(stream),
        media_type="text/plain; charset=utf-8",
        # Stop nginx from buffering the stream.
        headers={"X-Accel-Buffering": "no"},
    )
