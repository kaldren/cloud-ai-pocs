#!/usr/bin/env bash
# Writes ../backend/.env from `terraform output`. Keyless: no secrets are written.
set -euo pipefail

cd "$(dirname "$0")"
env_file="../backend/.env"

keys=(
  AZURE_SEARCH_ENDPOINT
  AZURE_SEARCH_INDEX
  AZURE_OPENAI_ENDPOINT
  AZURE_OPENAI_CHAT_DEPLOYMENT
  AZURE_OPENAI_EMBEDDING_DEPLOYMENT
)

tmp="$(mktemp)"
for key in "${keys[@]}"; do
  value="$(terraform output -raw "$(echo "$key" | tr '[:upper:]' '[:lower:]')")"
  printf '%s=%s\n' "$key" "$value" >>"$tmp"
done
mv "$tmp" "$env_file"
echo "Wrote ${#keys[@]} keys to $env_file"
