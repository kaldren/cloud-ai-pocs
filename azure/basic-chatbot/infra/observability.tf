# ===========================================================================
# Foundry observability: project + Application Insights
#
# Telemetry lives in Application Insights, backed by the Log Analytics workspace
# in main.tf. The Foundry project's Traces and Monitoring views read from the
# Application Insights resource connected below.
# ===========================================================================

# ---------------------------------------------------------------------------
# Application Insights (workspace-based, same workspace as Container Apps logs)
# ---------------------------------------------------------------------------
resource "azurerm_application_insights" "this" {
  name                = "appi-${var.poc_name}"
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location
  workspace_id        = azurerm_log_analytics_workspace.this.id
  application_type    = "web"

  # Keyless: ingestion needs an Entra token (Monitoring Metrics Publisher), so the
  # connection string alone can't send data. It only tells the exporter where to send.
  local_authentication_enabled = false

  # COST: no charge of its own. Telemetry is billed as Log Analytics ingestion
  # (first 5 GB/month free), with the workspace's 30-day retention.

  tags = local.tags
}

# ---------------------------------------------------------------------------
# Foundry project: the portal's home for traces, monitoring, and evaluations.
# The Foundry portal had already created this default project, so it was
# imported (once) under the portal's name instead of creating a second one.
# ---------------------------------------------------------------------------
locals {
  # The portal's naming: account name minus its last character, plus "-project".
  foundry_project_name = "aif-${var.poc_name}-${substr(local.suffix, 0, 5)}-project"
}

resource "azurerm_cognitive_account_project" "this" {
  name                 = local.foundry_project_name
  cognitive_account_id = azurerm_cognitive_account.this.id
  location             = azurerm_resource_group.this.location
  display_name         = var.poc_name
  description          = "Observability (tracing, monitoring, evaluation) for ${var.poc_name}"

  identity {
    type = "SystemAssigned"
  }

  tags = local.tags
}

# ---------------------------------------------------------------------------
# Connect Application Insights to the project, which enables Foundry tracing.
# azurerm has no resource for project connections, so this uses azapi.
# ---------------------------------------------------------------------------
resource "azapi_resource" "project_app_insights_connection" {
  type      = "Microsoft.CognitiveServices/accounts/projects/connections@2026-03-01"
  name      = azurerm_application_insights.this.name
  parent_id = azurerm_cognitive_account_project.this.id

  body = {
    properties = {
      category = "AppInsights"
      target   = azurerm_application_insights.this.id
      # The connection string only allows sending telemetry, not reading it.
      # It ends up in the gitignored Terraform state, never in the repo.
      authType = "ApiKey"
      credentials = {
        key = azurerm_application_insights.this.connection_string
      }
      metadata = {
        ApiType    = "Azure"
        ResourceId = azurerm_application_insights.this.id
      }
    }
  }
}

# ---------------------------------------------------------------------------
# RBAC
# ---------------------------------------------------------------------------
# The backend sends telemetry with its managed identity (keyless ingestion).
resource "azurerm_role_assignment" "apps_monitoring_publisher" {
  scope                = azurerm_application_insights.this.id
  role_definition_name = "Monitoring Metrics Publisher"
  principal_id         = azurerm_user_assigned_identity.apps.principal_id
  principal_type       = "ServicePrincipal"
}

# Same for the developer, when the backend runs locally on `az login`.
resource "azurerm_role_assignment" "dev_monitoring_publisher" {
  scope                = azurerm_application_insights.this.id
  role_definition_name = "Monitoring Metrics Publisher"
  principal_id         = data.azurerm_client_config.current.object_id
}

# Read telemetry in the Foundry Traces view.
resource "azurerm_role_assignment" "dev_app_insights_log_reader" {
  scope                = azurerm_application_insights.this.id
  role_definition_name = "Log Analytics Reader"
  principal_id         = data.azurerm_client_config.current.object_id
}

# Register the backend as an external agent (app.register_agent). Formerly "Azure AI User".
resource "azurerm_role_assignment" "dev_foundry_user" {
  scope                = azurerm_cognitive_account_project.this.id
  role_definition_name = "Foundry User"
  principal_id         = data.azurerm_client_config.current.object_id
}
