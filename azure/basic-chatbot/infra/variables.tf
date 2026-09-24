variable "subscription_id" {
  description = "Azure subscription ID to deploy into. Set in the gitignored terraform.tfvars."
  type        = string
}

variable "poc_name" {
  description = "PoC name; used for the resource group (rg-<poc_name>), resource names, and the poc tag."
  type        = string
  default     = "basic-chatbot"
}

variable "location" {
  description = "Azure region for all resources."
  type        = string
  default     = "swedencentral"
}

variable "owner" {
  description = "Value of the owner tag (e.g. your email or alias)."
  type        = string
}

variable "created" {
  description = "Value of the created tag (YYYY-MM-DD)."
  type        = string
  default     = "2026-09-24"
}

variable "search_index_name" {
  description = "Name of the search index the backend creates. Terraform does not create the index."
  type        = string
  default     = "docs"
}

variable "chat_deployment_name" {
  description = "Deployment name for the chat model (gpt-4.1-mini)."
  type        = string
  default     = "gpt-4.1-mini"
}

variable "embedding_deployment_name" {
  description = "Deployment name for the embeddings model (text-embedding-3-small)."
  type        = string
  default     = "text-embedding-3-small"
}

variable "chat_capacity_ktpm" {
  description = "Chat deployment capacity in thousands of tokens per minute. Capacity is a rate limit, not a cost."
  type        = number
  default     = 30
}

variable "embedding_capacity_ktpm" {
  description = "Embedding deployment capacity in thousands of tokens per minute. Capacity is a rate limit, not a cost."
  type        = number
  default     = 30
}
