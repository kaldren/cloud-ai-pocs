from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.rag import chunking, index, ingest

SAMPLE = Path(__file__).resolve().parents[2] / "data" / "sample" / "brightmoor-employee-handbook.md"


def _doc(sections: int, paragraphs: int) -> str:
    parts = ["# Title"]
    for s in range(sections):
        parts.append(f"## Section {s}")
        parts.extend(f"Paragraph {s}.{p} " + "word " * 60 for p in range(paragraphs))
    return "\n\n".join(parts)


def test_extract_title() -> None:
    assert chunking.extract_title("intro\n\n# My Doc\n\n## Part") == "My Doc"
    assert chunking.extract_title("## No h1") is None


def test_split_blocks_tracks_section_path() -> None:
    blocks = chunking.split_blocks("# T\n\n## A\n\ntext a\n\n### A1\n\ntext a1\n\n## B\n\ntext b")
    body = {b.text: b.section for b in blocks if not b.is_heading}
    assert body == {"text a": "A", "text a1": "A > A1", "text b": "B"}


def test_chunks_respect_max_tokens_and_overlap() -> None:
    chunks = chunking.chunk_markdown(
        _doc(sections=2, paragraphs=12), max_tokens=200, overlap_tokens=70
    )

    assert len(chunks) > 2
    assert all(chunking.count_tokens(c) <= 200 + 20 for c in chunks)  # + section prefix
    # A continuation chunk repeats the previous chunk's last paragraph and names its section.
    continuation = next(c for c in chunks[1:] if c.startswith("Section: "))
    previous = chunks[chunks.index(continuation) - 1]
    assert previous.split("\n\n")[-1] in continuation


def test_new_section_starts_new_chunk_without_overlap() -> None:
    chunks = chunking.chunk_markdown(
        _doc(sections=3, paragraphs=3), max_tokens=250, overlap_tokens=70
    )

    # Section 0 shares its chunk with the H1; later sections open a fresh chunk.
    assert chunks[0].startswith("# Title\n\n## Section 0")
    assert all(any(c.startswith(f"## Section {s}") for c in chunks) for s in (1, 2))
    assert not any(c.rstrip().endswith(("## Section 1", "## Section 2")) for c in chunks)


def test_oversized_block_is_split() -> None:
    chunks = chunking.chunk_markdown("# T\n\n" + "token " * 1000, max_tokens=200, overlap_tokens=20)
    assert len(chunks) >= 5
    assert all(chunking.count_tokens(c) <= 200 for c in chunks)


def test_chunk_markdown_rejects_bad_sizes() -> None:
    with pytest.raises(ValueError):
        chunking.chunk_markdown("x", max_tokens=100, overlap_tokens=100)


def test_sample_document_produces_several_chunks() -> None:
    chunks = ingest.build_chunks(SAMPLE.read_text(encoding="utf-8"), SAMPLE.name, "fallback")

    assert len(chunks) >= 5
    assert {c.title for c in chunks} == {"Brightmoor Kinetics Employee Handbook"}
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
    assert chunks[0].id == "brightmoor-employee-handbook_md-0000"


def test_chunk_ids_are_deterministic_and_key_safe() -> None:
    assert ingest.chunk_id("a b/c.md", 3) == "a_b_c_md-0003"
    assert ingest.chunk_id("a b/c.md", 3) == ingest.chunk_id("a b/c.md", 3)


def test_index_schema() -> None:
    idx = index.build_index("docs")
    fields = {f.name: f for f in idx.fields}

    assert set(fields) == {"id", "content", "title", "source", "chunk_index", "content_vector"}
    assert fields["id"].key
    assert fields["content"].searchable
    assert fields["source"].filterable
    vector = fields["content_vector"]
    assert vector.type == "Collection(Edm.Single)"
    assert vector.vector_search_dimensions == 1536
    assert vector.vector_search_profile_name == index.VECTOR_PROFILE_NAME
    assert idx.vector_search is not None
    assert idx.semantic_search is not None


def test_embed_texts_batches_and_orders() -> None:
    client = MagicMock()

    def create(model: str, input: list[str]) -> SimpleNamespace:
        data = [
            SimpleNamespace(index=i, embedding=[float(len(t))] * index.EMBEDDING_DIMENSIONS)
            for i, t in enumerate(input)
        ]
        return SimpleNamespace(data=list(reversed(data)))

    client.embeddings.create.side_effect = create
    vectors = ingest.embed_texts(client, "emb", ["a", "bb", "ccc"], batch_size=2)

    assert client.embeddings.create.call_count == 2
    assert [v[0] for v in vectors] == [1.0, 2.0, 3.0]


def test_delete_stale_chunks_only_deletes_unknown_ids() -> None:
    client = MagicMock()
    client.search.return_value = [{"id": "s-0000"}, {"id": "s-0001"}, {"id": "s-0002"}]

    removed = ingest.delete_stale_chunks(client, "it's.md", {"s-0000", "s-0001"})

    assert removed == 1
    assert client.search.call_args.kwargs["filter"] == "source eq 'it''s.md'"
    client.delete_documents.assert_called_once_with(documents=[{"id": "s-0002"}])
