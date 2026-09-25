"""Ingest markdown files into the Azure AI Search index: chunk, embed, upload.

Usage (from backend/):
    uv run python -m app.rag.ingest ../data/sample/brightmoor-employee-handbook.md [more files]

Idempotent: the index is created or updated in place, chunk ids are deterministic
(`<source>-<chunk_index>`), uploads use merge-or-upload, and chunks left over from an earlier,
longer version of the same source are deleted.
"""

import argparse
import logging
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from azure.search.documents import SearchClient
from openai import OpenAI

from app.azure_clients import (
    build_openai_client,
    build_search_client,
    build_search_index_client,
    get_credential,
)
from app.config import Settings, get_settings
from app.rag.chunking import (
    DEFAULT_MAX_TOKENS,
    DEFAULT_OVERLAP_TOKENS,
    chunk_markdown,
    extract_title,
)
from app.rag.index import (
    EMBEDDING_DIMENSIONS,
    FIELD_CHUNK_INDEX,
    FIELD_CONTENT,
    FIELD_CONTENT_VECTOR,
    FIELD_ID,
    FIELD_SOURCE,
    FIELD_TITLE,
    ensure_index,
)

logger = logging.getLogger(__name__)

EMBEDDING_BATCH_SIZE = 16
UPLOAD_BATCH_SIZE = 100

_KEY_UNSAFE = re.compile(r"[^A-Za-z0-9_\-=]")


@dataclass(frozen=True)
class Chunk:
    id: str
    title: str
    source: str
    chunk_index: int
    content: str


def chunk_id(source: str, index: int) -> str:
    """Deterministic document key; search keys allow only letters, digits, `_`, `-`, `=`."""
    return f"{_KEY_UNSAFE.sub('_', source)}-{index:04d}"


def build_chunks(
    text: str,
    source: str,
    fallback_title: str,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
) -> list[Chunk]:
    title = extract_title(text) or fallback_title
    return [
        Chunk(id=chunk_id(source, i), title=title, source=source, chunk_index=i, content=content)
        for i, content in enumerate(chunk_markdown(text, max_tokens, overlap_tokens))
    ]


def embed_texts(
    client: OpenAI, deployment: str, texts: Sequence[str], batch_size: int = EMBEDDING_BATCH_SIZE
) -> list[list[float]]:
    vectors: list[list[float]] = []
    for start in range(0, len(texts), batch_size):
        batch = list(texts[start : start + batch_size])
        response = client.embeddings.create(model=deployment, input=batch)
        vectors.extend(item.embedding for item in sorted(response.data, key=lambda d: d.index))
    for vector in vectors:
        if len(vector) != EMBEDDING_DIMENSIONS:
            raise ValueError(f"expected {EMBEDDING_DIMENSIONS} dimensions, got {len(vector)}")
    return vectors


def to_documents(
    chunks: Sequence[Chunk], vectors: Sequence[Sequence[float]]
) -> list[dict[str, object]]:
    if len(chunks) != len(vectors):
        raise ValueError("chunks and vectors differ in length")
    return [
        {
            FIELD_ID: chunk.id,
            FIELD_TITLE: chunk.title,
            FIELD_SOURCE: chunk.source,
            FIELD_CHUNK_INDEX: chunk.chunk_index,
            FIELD_CONTENT: chunk.content,
            FIELD_CONTENT_VECTOR: list(vector),
        }
        for chunk, vector in zip(chunks, vectors, strict=True)
    ]


def upload_documents(client: SearchClient, documents: Sequence[dict[str, object]]) -> None:
    for start in range(0, len(documents), UPLOAD_BATCH_SIZE):
        batch = [dict(doc) for doc in documents[start : start + UPLOAD_BATCH_SIZE]]
        # The SDK annotates documents as a bare List[Dict]; ours are dict[str, Any].
        results = client.merge_or_upload_documents(documents=batch)  # pyright: ignore[reportUnknownMemberType]
        failed = [r.key for r in results if not r.succeeded]
        if failed:
            raise RuntimeError(f"failed to index {len(failed)} chunks: {failed}")


def delete_stale_chunks(client: SearchClient, source: str, keep_ids: set[str]) -> int:
    """Delete chunks of `source` that are not in `keep_ids` (left over from a longer version)."""
    escaped = source.replace("'", "''")
    results = cast(
        Iterable[dict[str, Any]],
        client.search(  # pyright: ignore[reportUnknownMemberType]
            search_text="*", filter=f"{FIELD_SOURCE} eq '{escaped}'", select=[FIELD_ID]
        ),
    )
    stale: list[dict[str, object]] = [
        {FIELD_ID: doc[FIELD_ID]} for doc in results if doc[FIELD_ID] not in keep_ids
    ]
    if stale:
        client.delete_documents(documents=stale)  # pyright: ignore[reportUnknownMemberType]
    return len(stale)


def ingest_file(
    path: Path,
    settings: Settings,
    search_client: SearchClient,
    openai_client: OpenAI,
) -> int:
    """Chunk, embed, and upload one markdown file. Returns the number of chunks."""
    source = path.name
    chunks = build_chunks(path.read_text(encoding="utf-8"), source, fallback_title=path.stem)
    if not chunks:
        logger.warning("No content in %s; skipping", path)
        return 0
    logger.info("Chunked %s into %d chunks", source, len(chunks))

    vectors = embed_texts(
        openai_client, settings.azure_openai_embedding_deployment, [c.content for c in chunks]
    )
    upload_documents(search_client, to_documents(chunks, vectors))
    removed = delete_stale_chunks(search_client, source, {c.id for c in chunks})
    logger.info("Uploaded %d chunks from %s (removed %d stale)", len(chunks), source, removed)
    return len(chunks)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest markdown files into Azure AI Search.")
    parser.add_argument("paths", nargs="+", type=Path, help="Markdown files to ingest")
    args = parser.parse_args(argv)
    paths: list[Path] = args.paths

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    # The Azure SDK logs every HTTP request at INFO; keep the output readable.
    logging.getLogger("azure").setLevel(logging.WARNING)
    for name in ("httpx", "httpx2"):
        logging.getLogger(name).setLevel(logging.WARNING)

    missing = [p for p in paths if not p.is_file()]
    if missing:
        parser.error(f"not a file: {', '.join(map(str, missing))}")

    settings = get_settings()
    credential = get_credential()
    index_client = build_search_index_client(settings, credential)
    index = ensure_index(index_client, settings.azure_search_index)
    logger.info("Index %r is ready", index.name)

    search_client = build_search_client(settings, credential)
    openai_client = build_openai_client(settings, credential)
    total = sum(ingest_file(p, settings, search_client, openai_client) for p in paths)
    logger.info("Done: %d chunks from %d file(s) in index %r", total, len(paths), index.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
