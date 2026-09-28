"""Register the backend in Foundry as an external agent, so its traces show under Agents.

Usage (from backend/):
    uv run python -m app.register_agent

Foundry stores only metadata; it never calls the backend. The portal matches traces to the
agent by `gen_ai.agent.id`, which app.telemetry sets to FOUNDRY_AGENT_NAME on every span.
Safe to re-run: registering an existing name adds a revision to the same agent.
External agents are in preview, hence `allow_preview=True`.
"""

import logging

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import ExternalAgentDefinition

from app.azure_clients import get_credential
from app.config import get_settings

logger = logging.getLogger(__name__)

DESCRIPTION = "RAG chatbot (FastAPI on Container Apps): Azure AI Search + gpt-4.1-mini."


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("azure").setLevel(logging.WARNING)

    settings = get_settings()
    if settings.foundry_project_endpoint is None:
        logger.error("FOUNDRY_PROJECT_ENDPOINT is not set (see infra/write-env.sh)")
        return 1

    with AIProjectClient(
        endpoint=str(settings.foundry_project_endpoint),
        credential=get_credential(),
        allow_preview=True,
    ) as project:
        agent = project.agents.create_version(
            agent_name=settings.foundry_agent_name,
            description=DESCRIPTION,
            definition=ExternalAgentDefinition(otel_agent_id=settings.foundry_agent_name),
        )
    logger.info("Registered external agent %r (gen_ai.agent.id = %r)", agent.name, agent.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
