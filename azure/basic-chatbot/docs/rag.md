# RAG with Azure AI Search

Ingestion and retrieval-augmented chat are both implemented.

## Ingest
```bash
cd backend
uv run python -m app.rag.ingest ../data/sample/brightmoor-employee-handbook.md
```
Creates or updates the `docs` index (`app/rag/index.py`), splits markdown into chunks of about 500
tokens with 75 tokens of overlap (`app/rag/chunking.py`), embeds them with text-embedding-3-small,
and merge-uploads them with deterministic ids (`<source>-<NNNN>`). Re-running it is safe.
`data/sample/` holds a fictional handbook for testing grounding.

## Flow
1. **Ingest** – documents are chunked, embedded, and pushed to an Azure AI Search index.
2. **Retrieve** – on each chat message the backend queries the index (hybrid: keyword + vector).
3. **Generate** – top chunks are added to the LLM prompt as context; the answer is returned with sources.

## Retrieve (`app/rag/retrieve.py`)
On every `POST /chat`, before streaming starts:
- The keyword part (`search_text`) is the latest user message, capped at 1000 characters.
- The vector part embeds the previous and latest user messages with text-embedding-3-small, so a
  follow-up like "And in Paris?" keeps its context. The index has no integrated vectorizer, so
  the backend embeds queries itself.
- One hybrid query runs: `search_text` plus a `VectorizedQuery` on `content_vector`, with
  `top = k_nearest_neighbors = RAG_TOP_K` (default 5). Search fuses both result lists with
  Reciprocal Rank Fusion. The semantic ranker is disabled on the service, so no
  `query_type=semantic`.
- Results are read in full and validated. A Search, credential, or embedding failure returns
  `502 {"detail": "Upstream search error"}` and is logged, so the client never gets a partial
  answer.

## Generate (`app/rag/prompt.py`)
- The system prompt tells the model to answer only from the sources, cite them inline as
  `[1]`, `[2]`, and say it doesn't know when the sources don't cover the question. Sources are
  treated as data, not instructions.
- The retrieved chunks follow the prompt as numbered sources inside `<sources>…</sources>`,
  each as `[n] <title> (<source>)` followed by the chunk text. With no hits, the block says no
  matching documents were found.
- The reply streams as `text/plain`. After a clean finish, the backend appends a plain-text
  footer that lists only the sources the reply cited:
  ```
  …plus a one-off bonus of €400 [1].

  Sources:
  [1] Brightmoor Kinetics Employee Handbook (brightmoor-employee-handbook.md)
  ```
  A reply that cites nothing gets no footer. If the model stream fails part-way, the footer is
  also skipped. Footers in earlier assistant turns are stripped before the history goes back to
  the model.

## Azure resources
- Azure AI Search service (Basic); the backend creates the `docs` index
- Foundry account with `gpt-4.1-mini` (chat) and `text-embedding-3-small` (embeddings)
- All keyless (RBAC); provisioned by `infra/`

## Config
See `backend/.env.example`.
