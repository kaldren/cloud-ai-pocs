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
