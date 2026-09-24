# RAG with Azure AI Search (planned)

Not implemented yet.

## Flow
1. **Ingest** – documents are chunked, embedded, and pushed to an Azure AI Search index.
2. **Retrieve** – on each chat message the backend queries the index (hybrid: keyword + vector).
3. **Generate** – top chunks are added to the LLM prompt as context; the answer is returned with sources.

## Azure resources
- Azure AI Search service + index
- An LLM / embeddings endpoint (TBD)

## Config
See `backend/.env.example`.
