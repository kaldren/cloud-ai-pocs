from dataclasses import dataclass
from typing import cast

import pytest
from azure.core.exceptions import HttpResponseError
from azure.search.documents.models import VectorizedQuery
from openai import OpenAI

from app.chat import ChatRequest
from app.rag.retrieve import (
    MAX_SEARCH_TEXT_CHARS,
    RetrievalError,
    RetrievedChunk,
    build_query,
    embed_query,
    retrieve,
)
from tests.fakes import FakeEmbeddings, FakeSearchClient, hit

VECTOR = [0.25] * 1536


def request(*turns: str) -> ChatRequest:
    """Alternating user / assistant turns, ending with a user turn."""
    roles = ["user", "assistant"]
    return ChatRequest.model_validate(
        {"messages": [{"role": roles[i % 2], "content": t} for i, t in enumerate(turns)]}
    )


def fixed_embed(text: str) -> list[float]:
    return VECTOR


def test_query_uses_latest_turn_for_keywords_and_prior_turn_for_vectors() -> None:
    query = build_query(request("Hotel cap in London?", "It is 250 GBP [1].", " And Paris? "))

    assert query.search_text == "And Paris?"
    assert query.embedding_text == "Hotel cap in London?\nAnd Paris?"


def test_query_truncates_long_keyword_text() -> None:
    query = build_query(request("x" * 5000))

    assert len(query.search_text) == MAX_SEARCH_TEXT_CHARS
    assert len(query.embedding_text) == 5000


def test_runs_hybrid_query_with_top_k() -> None:
    search = FakeSearchClient(hits=[hit(3, "Recharge Week"), hit(1)])

    chunks = retrieve(search, fixed_embed, request("When is Recharge Week?"), top_k=4)

    assert chunks == [
        RetrievedChunk("handbook_md-0003", "Handbook", "handbook.md", 3, "Recharge Week"),
        RetrievedChunk("handbook_md-0001", "Handbook", "handbook.md", 1, "chunk 1"),
    ]
    [call] = search.calls
    assert call["search_text"] == "When is Recharge Week?"
    assert call["top"] == 4
    assert call["select"] == ["id", "title", "source", "chunk_index", "content"]
    [vector_query] = call["vector_queries"]
    assert isinstance(vector_query, VectorizedQuery)
    assert vector_query.vector == VECTOR
    assert vector_query.k_nearest_neighbors == 4
    assert vector_query.fields == "content_vector"


def test_no_hits_returns_empty_list() -> None:
    assert retrieve(FakeSearchClient(), fixed_embed, request("Tokyo hotel cap?"), top_k=5) == []


def test_search_error_propagates_while_reading_results() -> None:
    search = FakeSearchClient(error=HttpResponseError("503"))

    with pytest.raises(HttpResponseError):
        retrieve(search, fixed_embed, request("Hi"), top_k=5)


def test_malformed_hit_raises_retrieval_error() -> None:
    search = FakeSearchClient(hits=[{"id": "x", "content": "no title"}])

    with pytest.raises(RetrievalError):
        retrieve(search, fixed_embed, request("Hi"), top_k=5)


@dataclass
class FakeOpenAI:
    embeddings: FakeEmbeddings


def test_embed_query_uses_deployment_and_returns_vector() -> None:
    embeddings = FakeEmbeddings()
    client = cast(OpenAI, FakeOpenAI(embeddings))

    vector = embed_query(client, "text-embedding-3-small", "question")

    assert len(vector) == 1536
    assert embeddings.inputs == ["question"]


def test_embed_query_rejects_wrong_dimensions() -> None:
    client = cast(OpenAI, FakeOpenAI(FakeEmbeddings(dimensions=3)))

    with pytest.raises(RetrievalError, match="1536"):
        embed_query(client, "text-embedding-3-small", "question")
