---
name: new-poc
description: Creates a new PoC end to end. It researches the cloud services, scaffolds <cloud>/<poc-name>/, writes Terraform, registers the PoC in the cloud README, and verifies it. Use it when the user wants to start a new PoC.
argument-hint: <azure|gcp|aws> <poc-name> "<one-line idea>"
---

# New PoC

Arguments: `$ARGUMENTS` (cloud, kebab-case PoC name, one-line idea).

Follow the conventions in `AGENTS.md` throughout. Use `azure/basic-chatbot/` as the reference for layout and README style.

## 1. Clarify
If any of the following are missing or ambiguous, ask in a single AskUserQuestion: which cloud AI services, whether it needs a UI (default: FastAPI backend only), the region, and whether cloud resources are needed at all. Check that `<cloud>/<poc-name>/` does not already exist.

## 2. Research
Start the **cloud-researcher** agent with the cloud, the services, and the intended use. Save its brief as `<cloud>/<poc-name>/docs/research.md`, keeping the sources. If its Unknowns block a decision, ask the user.

## 3. Scaffold
Create the PoC yourself (in the main session), modelled on `azure/basic-chatbot/`:
- `README.md` with a summary, a Tech stack table, Structure, and Run.
- `backend/`: create it with `uv init`, then `uv add` the SDKs from the research brief plus `pydantic-settings`, and `uv add --dev ruff mypy pytest`. Add `.python-version`, a settings module, `.env.example` from the brief's Env vars block, a minimal app with a health endpoint, and at least one test in `tests/`.
- `frontend/` only if a UI was requested.
- `docs/` for design notes.
Keep it minimal: this is a PoC skeleton, not the feature.

## 4. Infra
If cloud resources are needed:
- **azure**: start the **azure-infra** agent in plan mode for `azure/<poc-name>`. Show the user its MCP findings, plan summary, and cost estimate. **Only after the user explicitly approves**, start **azure-infra** again in apply mode, and say that the user approved.
- **gcp / aws**: start the **infra-author** agent for `<cloud>/<poc-name>`. Show the user its plan summary and cost estimate. Run `terraform apply` or the write-env script **only after the user explicitly approves**.

## 5. Register
Add a row to the PoC table in `<cloud>/README.md` (status `Scaffold`).

## 6. Verify
Start the **poc-verifier** agent on `<cloud>/<poc-name>`. Fix everything on its fix list, then run it again. Repeat until it returns `READY`, or until the only remaining items need real credentials. Report the final table to the user.
