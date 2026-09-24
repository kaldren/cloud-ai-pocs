terraform {
  required_version = ">= 1.9"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.81"
    }
  }
  # Local state on purpose (PoC). State files are gitignored at the repo root.
}

provider "azurerm" {
  features {
    cognitive_account {
      # Purge on destroy so the custom subdomain can be reused right away.
      purge_soft_delete_on_destroy = true
    }
  }
  subscription_id = var.subscription_id
}

data "azurerm_client_config" "current" {}

locals {
  # Deterministic suffix for globally unique names (no extra provider needed).
  suffix = substr(sha1("${var.subscription_id}-${var.poc_name}"), 0, 6)

  tags = {
    poc     = var.poc_name
    owner   = var.owner
    created = var.created
  }
}

resource "azurerm_resource_group" "this" {
  name     = "rg-${var.poc_name}"
  location = var.location
  tags     = local.tags
}

# ---------------------------------------------------------------------------
# Azure AI Search
# ---------------------------------------------------------------------------
resource "azurerm_search_service" "this" {
  name                = "srch-${var.poc_name}-${local.suffix}"
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location

  # COST: Basic is the cheapest tier with an SLA-free, always-on service that
  # supports vector + hybrid search at PoC scale (~USD 75/month, billed hourly).
  # Free tier is capped at 1 per subscription and 50 MB.
  sku             = "basic"
  replica_count   = 1
  partition_count = 1

  # Keyless: RBAC only, API keys disabled.
  local_authentication_enabled = false

  tags = local.tags
}

# ---------------------------------------------------------------------------
# Foundry (AIServices) account + OpenAI model deployments
# ---------------------------------------------------------------------------
resource "azurerm_cognitive_account" "this" {
  name                = "aif-${var.poc_name}-${local.suffix}"
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location
  kind                = "AIServices"

  # COST: S0 has no fixed fee; you pay per token on the deployments below.
  sku_name = "S0"

  # Required for Entra ID (keyless) auth.
  custom_subdomain_name = "aif-${var.poc_name}-${local.suffix}"

  # Keyless: API keys disabled.
  local_auth_enabled = false

  tags = local.tags
}

# COST: GlobalStandard is the cheapest real-time (pay-per-token) deployment
# type for both models in swedencentral. Note: Global routing may process
# prompts outside the EU; switch to DataZoneStandard for EU data-zone residency.
resource "azurerm_cognitive_deployment" "chat" {
  name                 = var.chat_deployment_name
  cognitive_account_id = azurerm_cognitive_account.this.id

  model {
    format  = "OpenAI"
    name    = "gpt-4.1-mini"
    version = "2025-04-14"
  }

  sku {
    name     = "GlobalStandard"
    capacity = var.chat_capacity_ktpm
  }

  version_upgrade_option = "NoAutoUpgrade"
}

resource "azurerm_cognitive_deployment" "embedding" {
  name                 = var.embedding_deployment_name
  cognitive_account_id = azurerm_cognitive_account.this.id

  model {
    format  = "OpenAI"
    name    = "text-embedding-3-small"
    version = "1"
  }

  sku {
    name     = "GlobalStandard"
    capacity = var.embedding_capacity_ktpm
  }

  version_upgrade_option = "NoAutoUpgrade"

  # Deployments on one account must be created one at a time.
  depends_on = [azurerm_cognitive_deployment.chat]
}

# ---------------------------------------------------------------------------
# Data-plane RBAC for the developer running Terraform (keyless local dev)
# ---------------------------------------------------------------------------
resource "azurerm_role_assignment" "dev_search_index_data_contributor" {
  scope                = azurerm_search_service.this.id
  role_definition_name = "Search Index Data Contributor"
  principal_id         = data.azurerm_client_config.current.object_id
}

# Needed for the backend to create/update the index definition.
resource "azurerm_role_assignment" "dev_search_service_contributor" {
  scope                = azurerm_search_service.this.id
  role_definition_name = "Search Service Contributor"
  principal_id         = data.azurerm_client_config.current.object_id
}

resource "azurerm_role_assignment" "dev_openai_user" {
  scope                = azurerm_cognitive_account.this.id
  role_definition_name = "Cognitive Services OpenAI User"
  principal_id         = data.azurerm_client_config.current.object_id
}
