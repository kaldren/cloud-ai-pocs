# basic-chatbot

Basic RAG chatbot on Azure: a React UI talks to a FastAPI backend, which grounds answers in documents retrieved from **Azure AI Search**.

## Tech stack
| Layer    | Tech                          |
| -------- | ----------------------------- |
| Frontend | React + Vite                  |
| Backend  | Python, FastAPI, uv           |
| RAG      | Azure AI Search (retrieval)   |
| LLM      | Foundry: gpt-4.1-mini, text-embedding-3-small |
| Auth     | Keyless (Entra ID, `DefaultAzureCredential`) |
| Infra    | Terraform (`infra/`)          |

See [`docs/rag.md`](docs/rag.md) for the planned RAG design.

## Structure
```
frontend/   React app (Vite)
backend/    FastAPI app
  app/config.py         Settings from env / .env
  app/azure_clients.py  Keyless Search + OpenAI clients
  app/rag/  Azure AI Search retrieval (planned)
infra/      Terraform (see infra/README.md)
docs/       Design notes
```

## Run
Provision Azure first (see [`infra/README.md`](infra/README.md)). `infra/write-env.sh` writes `backend/.env`. Auth uses your `az login`.
```bash
# backend
cd backend && uv sync
uv run uvicorn app.main:app --reload   # http://localhost:8000

# frontend
cd frontend && npm install && npm run dev   # http://localhost:5173
```
