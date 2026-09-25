#!/usr/bin/env bash
# Builds the backend and frontend images in ACR (az acr build, no local Docker
# needed) and rolls both container apps to the new tag.
# Run after `terraform apply` and `./write-env.sh`. Requires `az login`.
set -euo pipefail

cd "$(dirname "$0")"

acr="$(terraform output -raw acr_name)"
login_server="$(terraform output -raw acr_login_server)"
rg="$(terraform output -raw resource_group_name)"
backend_app="$(terraform output -raw backend_app_name)"
frontend_app="$(terraform output -raw frontend_app_name)"
frontend_url="$(terraform output -raw frontend_url)"
# The registry lives in the Terraform-pinned subscription, which may differ
# from the az CLI default.
subscription="$(awk -F'"' '/^[[:space:]]*subscription_id/ {print $2}' terraform.tfvars)"

tag="$(git rev-parse --short HEAD 2>/dev/null || date +%Y%m%d%H%M%S)"

echo "Building images with tag ${tag} in ${acr}"
az acr build --subscription "$subscription" --registry "$acr" \
  -t "basic-chatbot-api:${tag}" ../backend
az acr build --subscription "$subscription" --registry "$acr" \
  -t "basic-chatbot-web:${tag}" ../frontend

echo "Updating container apps"
az containerapp update --subscription "$subscription" -n "$backend_app" -g "$rg" \
  --image "${login_server}/basic-chatbot-api:${tag}" --output none
az containerapp update --subscription "$subscription" -n "$frontend_app" -g "$rg" \
  --image "${login_server}/basic-chatbot-web:${tag}" --output none

echo "Deployed ${tag}"
echo "Frontend: ${frontend_url}"
