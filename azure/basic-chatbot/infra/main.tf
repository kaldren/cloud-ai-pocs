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

# ===========================================================================
# Hosting: frontend + backend as containers in Azure Container Apps
# ===========================================================================

# ---------------------------------------------------------------------------
# Container registry (images built with `az acr build`, see deploy.sh)
# ---------------------------------------------------------------------------
resource "azurerm_container_registry" "this" {
  # Alphanumeric only, globally unique.
  name                = "acr${replace(var.poc_name, "-", "")}${local.suffix}"
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location

  # COST: Basic is the cheapest tier (~USD 5/month, 10 GB included).
  sku = "Basic"

  # Keyless: no admin user; pulls use the managed identity, pushes use Entra ID.
  admin_enabled = false

  tags = local.tags
}

# ---------------------------------------------------------------------------
# Log Analytics for the Container Apps environment
# ---------------------------------------------------------------------------
resource "azurerm_log_analytics_workspace" "this" {
  name                = "log-${var.poc_name}"
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location

  # COST: pay per GB ingested (first 5 GB/month per billing account free);
  # 30 days is the retention included at no extra charge.
  sku               = "PerGB2018"
  retention_in_days = 30

  tags = local.tags
}

# ---------------------------------------------------------------------------
# Container Apps environment (Consumption profile only)
# ---------------------------------------------------------------------------
resource "azurerm_container_app_environment" "this" {
  name                = "cae-${var.poc_name}"
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location

  # COST: Consumption plan, billed per vCPU-s / GiB-s while replicas run.
  # With min_replicas = 0 the apps scale to zero and stay within the free grant
  # at PoC volume.
  log_analytics_workspace_id = azurerm_log_analytics_workspace.this.id
  logs_destination           = "log-analytics"

  # Azure adds this default profile to every new environment. Declaring it keeps plans clean.
  workload_profile {
    name                  = "Consumption"
    workload_profile_type = "Consumption"
  }

  tags = local.tags
}

# ---------------------------------------------------------------------------
# User-assigned identity shared by both apps (ACR pull) and used by the
# backend for keyless Search + OpenAI calls.
# ---------------------------------------------------------------------------
resource "azurerm_user_assigned_identity" "apps" {
  name                = "id-${var.poc_name}"
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location
  tags                = local.tags
}

resource "azurerm_role_assignment" "apps_acr_pull" {
  scope                = azurerm_container_registry.this.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.apps.principal_id
  principal_type       = "ServicePrincipal"
}

resource "azurerm_role_assignment" "apps_openai_user" {
  scope                = azurerm_cognitive_account.this.id
  role_definition_name = "Cognitive Services OpenAI User"
  principal_id         = azurerm_user_assigned_identity.apps.principal_id
  principal_type       = "ServicePrincipal"
}

resource "azurerm_role_assignment" "apps_search_index_data_contributor" {
  scope                = azurerm_search_service.this.id
  role_definition_name = "Search Index Data Contributor"
  principal_id         = azurerm_user_assigned_identity.apps.principal_id
  principal_type       = "ServicePrincipal"
}

# Needed for the backend to create/update the index definition.
resource "azurerm_role_assignment" "apps_search_service_contributor" {
  scope                = azurerm_search_service.this.id
  role_definition_name = "Search Service Contributor"
  principal_id         = azurerm_user_assigned_identity.apps.principal_id
  principal_type       = "ServicePrincipal"
}

# Lets the developer push images (docker push); `az acr build` additionally
# needs scheduleRun/action, which Owner/Contributor on the subscription covers.
resource "azurerm_role_assignment" "dev_acr_push" {
  scope                = azurerm_container_registry.this.id
  role_definition_name = "AcrPush"
  principal_id         = data.azurerm_client_config.current.object_id
}

locals {
  # Public placeholder so the apps can be created before any image is pushed.
  # deploy.sh swaps in the real image; Terraform ignores image changes.
  bootstrap_image = "mcr.microsoft.com/k8se/quickstart:latest"
}

# ---------------------------------------------------------------------------
# Backend (FastAPI): internal ingress only, reachable from the frontend app.
# ---------------------------------------------------------------------------
resource "azurerm_container_app" "api" {
  name                         = "ca-${var.poc_name}-api"
  resource_group_name          = azurerm_resource_group.this.name
  container_app_environment_id = azurerm_container_app_environment.this.id
  revision_mode                = "Single"
  workload_profile_name        = "Consumption"

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.apps.id]
  }

  registry {
    server   = azurerm_container_registry.this.login_server
    identity = azurerm_user_assigned_identity.apps.id
  }

  ingress {
    external_enabled = false
    target_port      = 8000
    transport        = "auto"

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {
    # COST: scale to zero when idle.
    min_replicas = 0
    max_replicas = 1

    container {
      name   = "api"
      image  = local.bootstrap_image
      cpu    = 0.25
      memory = "0.5Gi"

      env {
        name  = "AZURE_SEARCH_ENDPOINT"
        value = "https://${azurerm_search_service.this.name}.search.windows.net"
      }
      env {
        name  = "AZURE_SEARCH_INDEX"
        value = var.search_index_name
      }
      env {
        name  = "AZURE_OPENAI_ENDPOINT"
        value = azurerm_cognitive_account.this.endpoint
      }
      env {
        name  = "AZURE_OPENAI_CHAT_DEPLOYMENT"
        value = azurerm_cognitive_deployment.chat.name
      }
      env {
        name  = "AZURE_OPENAI_EMBEDDING_DEPLOYMENT"
        value = azurerm_cognitive_deployment.embedding.name
      }
      # DefaultAzureCredential needs this to pick the user-assigned identity.
      env {
        name  = "AZURE_CLIENT_ID"
        value = azurerm_user_assigned_identity.apps.client_id
      }
    }
  }

  lifecycle {
    ignore_changes = [template[0].container[0].image]
  }

  tags = local.tags

  depends_on = [azurerm_role_assignment.apps_acr_pull]
}

# ---------------------------------------------------------------------------
# Frontend (nginx serving the React build, proxies /api/ to the backend).
# ---------------------------------------------------------------------------
resource "azurerm_container_app" "web" {
  name                         = "ca-${var.poc_name}-web"
  resource_group_name          = azurerm_resource_group.this.name
  container_app_environment_id = azurerm_container_app_environment.this.id
  revision_mode                = "Single"
  workload_profile_name        = "Consumption"

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.apps.id]
  }

  registry {
    server   = azurerm_container_registry.this.login_server
    identity = azurerm_user_assigned_identity.apps.id
  }

  ingress {
    external_enabled = true
    target_port      = 8080
    transport        = "auto"

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {
    # COST: scale to zero when idle.
    min_replicas = 0
    max_replicas = 1

    container {
      name   = "web"
      image  = local.bootstrap_image
      cpu    = 0.25
      memory = "0.5Gi"

      # Internal FQDN of the backend (<app>.internal.<env domain>).
      env {
        name  = "BACKEND_URL"
        value = "https://${azurerm_container_app.api.ingress[0].fqdn}"
      }
    }
  }

  lifecycle {
    ignore_changes = [template[0].container[0].image]
  }

  tags = local.tags

  depends_on = [azurerm_role_assignment.apps_acr_pull]
}
