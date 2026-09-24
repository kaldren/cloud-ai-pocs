# basic-chatbot

Basic RAG chatbot on Azure: a React UI talks to a FastAPI backend, which grounds answers in documents retrieved from **Azure AI Search**.

## Tech stack
| Layer    | Tech                          |
| -------- | ----------------------------- |
| Frontend | React + Vite                  |
| Backend  | Python, FastAPI, uv           |
| RAG      | Azure AI Search (retrieval)   |

See [`docs/rag.md`](docs/rag.md) for the planned RAG design.

## Structure
```
frontend/   React app (Vite)
backend/    FastAPI app
  app/rag/  Azure AI Search retrieval (planned)
docs/       Design notes
```

## Run
```bash
# backend
cd backend && uv sync && cp .env.example .env
uv run uvicorn app.main:app --reload   # http://localhost:8000

# frontend
cd frontend && npm install && npm run dev   # http://localhost:5173
```
