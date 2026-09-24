# cloud-ai-pocs

Independent AI PoCs grouped by cloud: `azure/`, `gcp/`, `aws/`.
Each PoC lives in `<cloud>/<poc-name>/` and defines its own structure and tech stack.
Never commit secrets.

## Python
Python projects use [uv](https://docs.astral.sh/uv/) by default.
- Dependencies live in `pyproject.toml`, installed with `uv add` / `uv add --dev`. Commit `uv.lock`. No `requirements.txt`, no bare `pip install`.
- Run things via `uv run` (e.g. `uv run pytest`); `uv sync` creates the `.venv`.
- Pin the Python version with `requires-python` and `.python-version`.
- Type hints on all functions; lint and format with `ruff`; type-check with `mypy` or `pyright`.
- Config from environment variables (via `pydantic-settings` or `python-dotenv`), never hardcoded; keep an `.env.example`.
- Tests with `pytest` in `tests/`.
- Small, focused modules; no logic at import time; use `logging`, not `print`.

## Agents & workflow
Start a new PoC with `/new-poc <cloud> <poc-name> "<idea>"` (`.claude/skills/new-poc/`). It runs these agents from `.claude/agents/`:
- `cloud-researcher`: checks current SDKs, models, regions, and pricing, and writes a cited brief to `docs/research.md`.
- `infra-author`: writes Terraform in `<poc>/infra/`. It runs only plan and validate; apply and destroy need the user's approval.
- `azure-infra`: Azure-specific infra. It uses the Azure MCP server (read-only) for live subscription context, writes Terraform, and applies only after the user approves.
- `python-developer`: writes and changes Python code under these conventions and leaves ruff, pyright, and pytest passing. Any PoC can use it directly.
- `poc-verifier`: an independent check against these conventions. It reports only.
Cloud resources go in one resource group (or project, or tag set) per PoC, tagged `poc`, `owner`, `created`.
