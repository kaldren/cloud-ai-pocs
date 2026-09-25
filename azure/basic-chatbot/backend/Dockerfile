FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS build
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=0
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY app ./app

FROM python:3.12-slim-bookworm AS runtime
RUN useradd --create-home --uid 1000 app
WORKDIR /app
COPY --from=build --chown=app:app /app /app
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# Local-only target (compose.yaml builds `target: local`). Adds the Azure CLI so
# DefaultAzureCredential can use the host's `az login` session, mounted read-only
# at /host-azure. Install steps follow the Microsoft Learn apt instructions.
FROM runtime AS local
USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl gnupg \
    && mkdir -p /etc/apt/keyrings \
    && curl -sLS https://packages.microsoft.com/keys/microsoft.asc \
       | gpg --dearmor -o /etc/apt/keyrings/microsoft.gpg \
    && chmod go+r /etc/apt/keyrings/microsoft.gpg \
    && . /etc/os-release \
    && printf 'Types: deb\nURIs: https://packages.microsoft.com/repos/azure-cli/\nSuites: %s\nComponents: main\nArchitectures: %s\nSigned-by: /etc/apt/keyrings/microsoft.gpg\n' \
       "$VERSION_CODENAME" "$(dpkg --print-architecture)" > /etc/apt/sources.list.d/azure-cli.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends azure-cli \
    && apt-get purge -y --auto-remove curl gnupg \
    && rm -rf /var/lib/apt/lists/*
COPY local-entrypoint.sh /usr/local/bin/local-entrypoint.sh
ENV AZURE_CONFIG_DIR=/home/app/.azure
USER app
ENTRYPOINT ["/usr/local/bin/local-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# Default target (az acr build / cloud): the lean runtime, no Azure CLI.
FROM runtime
