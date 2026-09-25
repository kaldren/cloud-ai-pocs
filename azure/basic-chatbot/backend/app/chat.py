"""Chat: request models, system prompt, and streaming a reply from Azure OpenAI."""

import logging
from collections.abc import Iterator
from enum import StrEnum
from typing import Annotated, Protocol, Self

from openai import OpenAI, OpenAIError
from openai.types.chat import ChatCompletionChunk, ChatCompletionMessageParam
from pydantic import BaseModel, Field, field_validator, model_validator

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = "You are a helpful assistant. Answer clearly and concisely."

MAX_MESSAGES = 50
MAX_CONTENT_CHARS = 8000


class Role(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class ChatMessage(BaseModel):
    role: Role
    content: Annotated[str, Field(max_length=MAX_CONTENT_CHARS)]

    @field_validator("content")
    @classmethod
    def content_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("content must not be blank")
        return value


class ChatRequest(BaseModel):
    messages: Annotated[list[ChatMessage], Field(min_length=1, max_length=MAX_MESSAGES)]

    @model_validator(mode="after")
    def last_message_from_user(self) -> Self:
        if self.messages[-1].role is not Role.USER:
            raise ValueError("the last message must have role 'user'")
        return self


class ChunkStream(Protocol):
    """What we need from `openai.Stream[ChatCompletionChunk]`; lets tests pass a plain fake."""

    def __iter__(self) -> Iterator[ChatCompletionChunk]: ...

    def close(self) -> None: ...


def build_messages(request: ChatRequest) -> list[ChatCompletionMessageParam]:
    """The conversation for the model, with our system prompt first."""
    messages: list[ChatCompletionMessageParam] = [{"role": "system", "content": SYSTEM_PROMPT}]
    for message in request.messages:
        if message.role is Role.USER:
            messages.append({"role": "user", "content": message.content})
        else:
            messages.append({"role": "assistant", "content": message.content})
    return messages


def start_stream(client: OpenAI, deployment: str, request: ChatRequest) -> ChunkStream:
    """Open the upstream stream. Raises on failure, before any bytes reach the client."""
    return client.chat.completions.create(
        model=deployment,
        messages=build_messages(request),
        stream=True,
    )


def iter_text(stream: ChunkStream) -> Iterator[str]:
    """Yield the reply's text deltas; a mid-stream upstream error is logged and ends the stream.

    Chunks without choices (Azure's content-filter preamble) or without content are skipped.
    """
    try:
        for chunk in stream:
            if not chunk.choices:
                continue
            content = chunk.choices[0].delta.content
            if content:
                yield content
    except OpenAIError:
        logger.exception("Upstream model error mid-stream; ending the response early")
    finally:
        stream.close()
