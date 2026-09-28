# Observability with Microsoft Foundry

Built up one step at a time. Done so far: **1. telemetry store** and **2. tracing**.

## How the pieces fit
```
backend (OpenTelemetry) --Entra ID--> Application Insights --> Log Analytics workspace
                                              ^
Foundry project --connection (AppInsights)----+   Traces view reads from here
Foundry "external agent" basic-chatbot  <-- matched by gen_ai.agent.id on every span
```
- **Application Insights** (`appi-basic-chatbot`) stores the telemetry. It is workspace-based, so
  the data lives in the same Log Analytics workspace as the Container Apps logs. Local auth is
  off, so the connection string alone can't send data. Senders need an Entra token and the
  Monitoring Metrics Publisher role.
- The **Foundry project** is connected to it (`infra/observability.tf`). That connection is what
  Foundry's Traces and Monitoring views read from.
- The backend is registered in Foundry as an **external agent** (preview). Foundry doesn't host
  or call it. It only matches incoming spans to the agent by `gen_ai.agent.id`.

## Tracing (`app/telemetry.py`)
Configured at startup when `APPLICATIONINSIGHTS_CONNECTION_STRING` is set. With it unset, as in
tests or a bare local run, tracing is off. Uses the
[Microsoft OpenTelemetry distro](https://github.com/microsoft/opentelemetry-distro-python), which
instruments the OpenAI SDK and the Azure SDK and exports to Application Insights.

One trace per chat turn:
```
POST /chat                             FastAPI server span (/health is excluded)
  invoke_agent basic-chatbot           the whole turn, until the last streamed byte
    embeddings text-embedding-3-small  query embedding, input tokens
    _SearchClientOperationsMixin...    hybrid search in Azure AI Search
    chat gpt-4.1-mini                  the streamed completion, input/output tokens
```
- `invoke_agent` follows the OpenTelemetry GenAI conventions. The route handler starts it, and
  `traced_reply` ends it once the stream finishes, because the reply streams after the handler
  returns.
- Token usage on the `chat` span needs `stream_options={"include_usage": True}`.
- `AgentIdSpanProcessor` stamps `gen_ai.agent.id` / `gen_ai.agent.name` on every span.
- The HTTP-client instrumentations (requests, urllib3, httpx, and httpx2, which the OpenAI SDK
  uses) and FastAPI's per-message `send`/`receive` spans are off. They only duplicated other
  spans, one per streamed token in the case of `send`.
- `sampling_ratio=1.0` keeps every trace whole. The distro's default sampler is rate-limited
  per span, so it dropped parts of each chat turn, even at PoC traffic.
- `GENAI_CAPTURE_CONTENT=true` records the conversation and the reply on the `invoke_agent` span
  (`gen_ai.input.messages` / `gen_ai.output.messages`), and turns on the OpenAI instrumentation's
  message events. It's on for this PoC because the data is a fictional handbook. Keep it off for
  real users.

## Register the agent (once)
```bash
cd backend
uv run python -m app.register_agent   # needs FOUNDRY_PROJECT_ENDPOINT (write-env.sh sets it)
```
Then, in [Foundry](https://ai.azure.com), open the project, go to **Agents**, select
**basic-chatbot**, and open **Traces**. Traces take 2–5 minutes to arrive.
