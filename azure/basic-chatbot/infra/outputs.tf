# One output per backend/.env key (lower-case names). write-env.sh maps them 1:1.

output "azure_search_endpoint" {
  description = "AZURE_SEARCH_ENDPOINT"
  value       = "https://${azurerm_search_service.this.name}.search.windows.net"
}

output "azure_search_index" {
  description = "AZURE_SEARCH_INDEX (created by the backend, not Terraform)"
  value       = var.search_index_name
}

output "azure_openai_endpoint" {
  description = "AZURE_OPENAI_ENDPOINT"
  value       = azurerm_cognitive_account.this.endpoint
}

output "azure_openai_chat_deployment" {
  description = "AZURE_OPENAI_CHAT_DEPLOYMENT"
  value       = azurerm_cognitive_deployment.chat.name
}

output "azure_openai_embedding_deployment" {
  description = "AZURE_OPENAI_EMBEDDING_DEPLOYMENT"
  value       = azurerm_cognitive_deployment.embedding.name
}

# ---------------------------------------------------------------------------
# Hosting outputs (NOT .env keys; write-env.sh ignores them, deploy.sh reads them)
# ---------------------------------------------------------------------------

output "acr_name" {
  description = "Container registry name (az acr build --registry)"
  value       = azurerm_container_registry.this.name
}

output "acr_login_server" {
  description = "Container registry login server (image prefix)"
  value       = azurerm_container_registry.this.login_server
}

output "resource_group_name" {
  description = "Resource group holding all PoC resources"
  value       = azurerm_resource_group.this.name
}

output "backend_app_name" {
  description = "Backend container app name"
  value       = azurerm_container_app.api.name
}

output "frontend_app_name" {
  description = "Frontend container app name"
  value       = azurerm_container_app.web.name
}

output "frontend_url" {
  description = "Public URL of the frontend"
  value       = "https://${azurerm_container_app.web.ingress[0].fqdn}"
}
