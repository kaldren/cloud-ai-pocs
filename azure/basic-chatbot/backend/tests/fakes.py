"""Fakes for the Search and OpenAI embedding clients (no network)."""

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

from azure.search.documents.models import VectorQuery

from app.rag.index import EMBEDDING_DIMENSIONS


def hit(n: int, content: str = "") -> dict[str, Any]:
    return {
        "id": f"handbook_md-{n:04d}",
        "title": "Handbook",
        "source": "handbook.md",
        "chunk_index": n,
        "content": content or f"chunk {n}",
        "@search.score": 0.5,
    }


@dataclass
class FakeSearchClient:
    hits: list[dict[str, Any]] = field(default_factory=list[dict[str, Any]])
    error: Exception | None = None
    calls: list[dict[str, Any]] = field(default_factory=list[dict[str, Any]])

    def search(
        self,
        search_text: str | None = None,
        *,
        select: list[str] | None = None,
        top: int | None = None,
        vector_queries: list[VectorQuery] | None = None,
    ) -> Iterator[Mapping[str, Any]]:
        self.calls.append(
            {
                "search_text": search_text,
                "select": select,
                "top": top,
                "vector_queries": vector_queries,
            }
        )
        # Like SearchItemPaged, fail lazily: the request happens on first iteration.
        if self.error is not None:
            raise self.error
        yield from self.hits


@dataclass
class FakeEmbeddings:
    dimensions: int = EMBEDDING_DIMENSIONS
    error: Exception | None = None
    inputs: list[str] = field(default_factory=list[str])

    def create(self, *, model: str, input: str) -> SimpleNamespace:
        self.inputs.append(input)
        if self.error is not None:
            raise self.error
        return SimpleNamespace(data=[SimpleNamespace(index=0, embedding=[0.1] * self.dimensions)])
