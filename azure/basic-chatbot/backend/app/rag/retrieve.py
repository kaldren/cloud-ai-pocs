"""Hybrid retrieval from the Azure AI Search index: BM25 over text plus HNSW over embeddings.

The index has no integrated vectorizer, so queries are embedded here with the same model used at
ingest (text-embedding-3-small). The semantic ranker is disabled on the service, so results are
ranked by Reciprocal Rank Fusion of the keyword and vector result lists.
"""

import logging
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from azure.search.documents.models import VectorizedQuery, VectorQuery
from openai import OpenAI
from pydantic import BaseModel, ValidationError

from app.chat import ChatRequest, Role
from app.rag.index import (
    EMBEDDING_DIMENSIONS,
    FIELD_CHUNK_INDEX,
    FIELD_CONTENT,
    FIELD_CONTENT_VECTOR,
    FIELD_ID,
    FIELD_SOURCE,
    FIELD_TITLE,
)

logger = logging.getLogger(__name__)

SELECT_FIELDS = [FIELD_ID, FIELD_TITLE, FIELD_SOURCE, FIELD_CHUNK_INDEX, FIELD_CONTENT]
# Keyword queries only need the question; long pasted text adds noise and query cost.
MAX_SEARCH_TEXT_CHARS = 1000

type Embedder = Callable[[str], list[float]]


class RetrievalError(Exception):
    """Search or embedding returned something we cannot use."""


class SearchBackend(Protocol):
    """The part of `azure.search.documents.SearchClient` that retrieval needs."""

    def search(
        self,
        search_text: str | None = None,
        *,
        select: list[str] | None = None,
        top: int | None = None,
        vector_queries: list[VectorQuery] | None = None,
    ) -> Iterable[Mapping[str, Any]]: ...  # Any: SDK documents are untyped JSON objects.


class _Hit(BaseModel):
    """A search result at the boundary; extra keys such as `@search.score` are ignored."""

    id: str
    title: str
    source: str
    chunk_index: int
    content: str


@dataclass(slots=True, frozen=True)
class RetrievedChunk:
    id: str
    title: str
    source: str
    chunk_index: int
    content: str


@dataclass(slots=True, frozen=True)
class RetrievalQuery:
    """`search_text` drives BM25; `embedding_text` adds the previous user turn for follow-ups."""

    search_text: str
    embedding_text: str


def build_query(request: ChatRequest) -> RetrievalQuery:
    user_turns = [m.content.strip() for m in request.messages if m.role is Role.USER]
    latest = user_turns[-1]
    embedding_text = "\n".join(user_turns[-2:])
    return RetrievalQuery(search_text=latest[:MAX_SEARCH_TEXT_CHARS], embedding_text=embedding_text)


def embed_query(client: OpenAI, deployment: str, text: str) -> list[float]:
    response = client.embeddings.create(model=deployment, input=text)
    if not response.data:
        raise RetrievalError("embedding response had no data")
    vector = response.data[0].embedding
    if len(vector) != EMBEDDING_DIMENSIONS:
        raise RetrievalError(f"expected {EMBEDDING_DIMENSIONS} dimensions, got {len(vector)}")
    return vector


def retrieve(
    search_client: SearchBackend, embed: Embedder, request: ChatRequest, top_k: int
) -> list[RetrievedChunk]:
    """Top `top_k` chunks for the conversation's latest user message, best first.

    Results are fully read here, so any Search error surfaces before a response starts streaming.
    """
    query = build_query(request)
    vector_query = VectorizedQuery(
        vector=embed(query.embedding_text),
        k_nearest_neighbors=top_k,
        fields=FIELD_CONTENT_VECTOR,
    )
    results = search_client.search(
        search_text=query.search_text,
        select=SELECT_FIELDS,
        top=top_k,
        vector_queries=[vector_query],
    )
    try:
        hits = [_Hit.model_validate(dict(doc)) for doc in results]
    except ValidationError as exc:
        raise RetrievalError("search returned a malformed document") from exc

    logger.info("Retrieved %d of top %d chunks", len(hits), top_k)
    logger.debug("Retrieved chunk ids: %s", [h.id for h in hits])
    return [RetrievedChunk(**hit.model_dump()) for hit in hits]
