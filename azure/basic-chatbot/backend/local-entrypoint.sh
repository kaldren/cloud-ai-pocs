#!/bin/sh
# Local image only: copy the host's read-only `az login` config into a writable
# AZURE_CONFIG_DIR (the CLI writes caches and logs there), then run the command.
set -eu

: "${AZURE_CONFIG_DIR:=/home/app/.azure}"
mkdir -p "$AZURE_CONFIG_DIR"
if [ -d /host-azure ]; then
  cp -R /host-azure/. "$AZURE_CONFIG_DIR"/ 2>/dev/null \
    || echo "local-entrypoint: some files in /host-azure could not be copied" >&2
else
  echo "local-entrypoint: /host-azure not mounted; Azure CLI credential unavailable" >&2
fi

exec "$@"
