terraform {
  required_version = ">= 1.5.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = ">= 3.90.0"
    }
  }

  # Backend configuration (remote state) can be added here as needed.
}

provider "azurerm" {
  features {}
  subscription_id = var.subscription_id
}

########################
# Resource Group
########################

resource "azurerm_resource_group" "rg" {
  name     = var.resource_group_name
  location = var.location

  tags = local.common_tags
}

########################
# Networking
########################

resource "azurerm_virtual_network" "vnet" {
  name                = "vnet-${var.project_name}-${var.environment}"
  address_space       = var.vnet_address_space
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name

  tags = local.common_tags
}

resource "azurerm_subnet" "subnet_app" {
  name                 = "PULSE-app-subnet"
  resource_group_name  = azurerm_resource_group.rg.name
  virtual_network_name = azurerm_virtual_network.vnet.name
  address_prefixes     = [var.subnet_app_prefix]

  delegation {
    name = "app-service-delegation"
    service_delegation {
      name    = "Microsoft.Web/serverFarms"
      actions = ["Microsoft.Network/virtualNetworks/subnets/action"]
    }
  }
}

resource "azurerm_subnet" "subnet_private_endpoints" {
  name                 = "PULSE-private-endpoints-subnet"
  resource_group_name  = azurerm_resource_group.rg.name
  virtual_network_name = azurerm_virtual_network.vnet.name
  address_prefixes     = [var.subnet_private_endpoints_prefix]
}

########################
# Azure OpenAI (Cognitive Account + Deployments via module)
########################

module "openai" {
  source              = "./modules/openai"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
  project_name        = var.project_name
  environment         = var.environment
  common_tags         = local.common_tags

  openai_sku_name = var.openai_sku_name

  openai_model_core_chat_id           = var.openai_model_core_chat_id
  openai_model_core_chat_version      = var.openai_model_core_chat_version
  openai_model_high_reasoning_id      = var.openai_model_high_reasoning_id
  openai_model_high_reasoning_version = var.openai_model_high_reasoning_version
  openai_model_audio_realtime_id      = var.openai_model_audio_realtime_id
  openai_model_audio_realtime_version = var.openai_model_audio_realtime_version
  openai_model_visual_asset_id        = var.openai_model_visual_asset_id
  openai_model_visual_asset_version   = var.openai_model_visual_asset_version

  openai_deployment_core_chat_sku           = var.openai_deployment_core_chat_sku
  openai_deployment_core_chat_capacity      = var.openai_deployment_core_chat_capacity
  openai_deployment_high_reasoning_sku      = var.openai_deployment_high_reasoning_sku
  openai_deployment_high_reasoning_capacity = var.openai_deployment_high_reasoning_capacity
  openai_deployment_audio_realtime_sku      = var.openai_deployment_audio_realtime_sku
  openai_deployment_audio_realtime_capacity = var.openai_deployment_audio_realtime_capacity
  openai_deployment_visual_asset_sku        = var.openai_deployment_visual_asset_sku
  openai_deployment_visual_asset_capacity   = var.openai_deployment_visual_asset_capacity
  enable_visual_asset_deployment            = var.enable_visual_asset_deployment
  openai_public_network_access_enabled      = var.openai_public_network_access_enabled
}

########################
# Azure Speech Services (Avatar)
########################

module "speech" {
  source              = "./modules/speech"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
  project_name        = var.project_name
  environment         = var.environment
  common_tags         = local.common_tags

  enable_speech_avatar = var.enable_speech_avatar
}

########################
# Azure OpenAI Private Endpoint & DNS
########################

resource "azurerm_private_dns_zone" "openai" {
  name                = "privatelink.openai.azure.com"
  resource_group_name = azurerm_resource_group.rg.name

  tags = local.common_tags
}

resource "azurerm_private_dns_zone_virtual_network_link" "openai_link" {
  name                  = "openai-dns-link"
  resource_group_name   = azurerm_resource_group.rg.name
  private_dns_zone_name = azurerm_private_dns_zone.openai.name
  virtual_network_id    = azurerm_virtual_network.vnet.id
}

resource "azurerm_private_endpoint" "openai" {
  name                = "pe-openai-${var.environment}"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  subnet_id           = azurerm_subnet.subnet_private_endpoints.id

  private_service_connection {
    name                           = "psc-openai-${var.environment}"
    private_connection_resource_id = module.openai.cognitive_account_id
    is_manual_connection           = false
    subresource_names              = ["account"]
  }

  private_dns_zone_group {
    name                 = "openai-dnszone-group"
    private_dns_zone_ids = [azurerm_private_dns_zone.openai.id]
  }

  tags = local.common_tags
}

########################
# Azure Speech Services Private Endpoint & DNS
########################

resource "azurerm_private_dns_zone" "speech" {
  count               = var.enable_speech_avatar ? 1 : 0
  name                = "privatelink.cognitiveservices.azure.com"
  resource_group_name = azurerm_resource_group.rg.name

  tags = local.common_tags
}

resource "azurerm_private_dns_zone_virtual_network_link" "speech_link" {
  count                 = var.enable_speech_avatar ? 1 : 0
  name                  = "speech-dns-link"
  resource_group_name   = azurerm_resource_group.rg.name
  private_dns_zone_name = azurerm_private_dns_zone.speech[0].name
  virtual_network_id    = azurerm_virtual_network.vnet.id
}

resource "azurerm_private_endpoint" "speech" {
  count               = var.enable_speech_avatar ? 1 : 0
  name                = "pe-speech-${var.environment}"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  subnet_id           = azurerm_subnet.subnet_private_endpoints.id

  private_service_connection {
    name                           = "psc-speech-${var.environment}"
    private_connection_resource_id = module.speech.speech_account_id
    is_manual_connection           = false
    subresource_names              = ["account"]
  }

  private_dns_zone_group {
    name                 = "speech-dnszone-group"
    private_dns_zone_ids = [azurerm_private_dns_zone.speech[0].id]
  }

  tags = local.common_tags
}

########################
# Storage Account & Containers
########################

resource "azurerm_storage_account" "storage" {
  name                     = var.storage_account_name
  resource_group_name      = azurerm_resource_group.rg.name
  location                 = azurerm_resource_group.rg.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  account_kind             = "StorageV2"

  public_network_access_enabled   = true
  shared_access_key_enabled       = true
  default_to_oauth_authentication = false
  min_tls_version                 = "TLS1_2"

  tags = merge(local.common_tags, {
    service_role = "content-and-logs"
  })
}

resource "azurerm_storage_container" "certification_materials" {
  name                  = "certification-materials"
  storage_account_name  = azurerm_storage_account.storage.name
  container_access_type = "private"
}

resource "azurerm_storage_container" "interaction_logs" {
  name                  = "interaction-logs"
  storage_account_name  = azurerm_storage_account.storage.name
  container_access_type = "private"
}

resource "azurerm_storage_container" "prompts" {
  name                  = "prompts"
  storage_account_name  = azurerm_storage_account.storage.name
  container_access_type = "private"
}

########################
# Storage Private Endpoint & DNS
########################

resource "azurerm_private_dns_zone" "blob" {
  name                = "privatelink.blob.core.windows.net"
  resource_group_name = azurerm_resource_group.rg.name

  tags = local.common_tags
}

resource "azurerm_private_dns_zone_virtual_network_link" "blob_link" {
  name                  = "blob-dns-link"
  resource_group_name   = azurerm_resource_group.rg.name
  private_dns_zone_name = azurerm_private_dns_zone.blob.name
  virtual_network_id    = azurerm_virtual_network.vnet.id
}

resource "azurerm_private_endpoint" "storage_blob" {
  name                = "pe-blob-${var.environment}"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  subnet_id           = azurerm_subnet.subnet_private_endpoints.id

  private_service_connection {
    name                           = "psc-blob-${var.environment}"
    private_connection_resource_id = azurerm_storage_account.storage.id
    is_manual_connection           = false
    subresource_names              = ["blob"]
  }

  private_dns_zone_group {
    name                 = "blob-dnszone-group"
    private_dns_zone_ids = [azurerm_private_dns_zone.blob.id]
  }

  tags = local.common_tags
}

########################
# App Service Plan
########################

# Managed inside module "app".

########################
# Application Insights & Log Analytics
########################

resource "azurerm_log_analytics_workspace" "log_analytics" {
  name                = "law-${var.project_name}-${var.environment}"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  sku                 = "PerGB2018"
  retention_in_days   = var.log_analytics_retention_days

  tags = local.common_tags
}

resource "azurerm_application_insights" "app_insights" {
  name                = "appi-${var.project_name}-${var.environment}"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  application_type    = "web"
  workspace_id        = azurerm_log_analytics_workspace.log_analytics.id

  tags = local.common_tags
}

########################
# Analytics PostgreSQL (Longitudinal & Readiness)
########################

module "analytics_postgres" {
  source              = "./modules/analytics_postgres"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
  project_name        = var.project_name
  environment         = var.environment
  common_tags         = local.common_tags

  virtual_network_name = azurerm_virtual_network.vnet.name
  virtual_network_id   = azurerm_virtual_network.vnet.id

  analytics_pg_subnet_prefix        = var.analytics_pg_subnet_prefix
  analytics_pg_version              = var.analytics_pg_version
  analytics_pg_sku_name             = var.analytics_pg_sku_name
  analytics_pg_storage_mb           = var.analytics_pg_storage_mb
  analytics_pg_backup_retention_days = var.analytics_pg_backup_retention_days
  analytics_pg_admin_username       = var.analytics_pg_admin_username
  analytics_pg_admin_password       = var.analytics_pg_admin_password
}

########################
# Web App + Function App (via module "app")
########################

module "app" {
  count               = var.enable_app_service ? 1 : 0
  source              = "./modules/app"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
  project_name        = var.project_name
  environment         = var.environment
  common_tags         = local.common_tags

  app_service_sku_name     = var.app_service_sku_name
  web_app_linux_fx_version = var.web_app_linux_fx_version
  subnet_app_id            = azurerm_subnet.subnet_app.id

  openai_endpoint                        = module.openai.endpoint
  openai_api_version                     = var.openai_api_version
  openai_api_key                         = module.openai.primary_key
  deployment_persona_core_chat_name      = module.openai.deployment_persona_core_chat_name
  deployment_persona_high_reasoning_name = module.openai.deployment_persona_high_reasoning_name
  deployment_PULSE_audio_realtime_name     = module.openai.deployment_PULSE_audio_realtime_name
  deployment_persona_visual_asset_name   = module.openai.deployment_persona_visual_asset_name

  storage_account_name                      = azurerm_storage_account.storage.name
  storage_account_primary_access_key        = azurerm_storage_account.storage.primary_access_key
  storage_account_primary_connection_string = azurerm_storage_account.storage.primary_connection_string
  storage_certification_container           = azurerm_storage_container.certification_materials.name
  storage_interaction_logs_container        = azurerm_storage_container.interaction_logs.name

  app_insights_connection_string = azurerm_application_insights.app_insights.connection_string

  analytics_pg_fqdn           = module.analytics_postgres.analytics_pg_fqdn
  analytics_pg_database_name  = module.analytics_postgres.analytics_pg_database_name
  analytics_pg_admin_username = var.analytics_pg_admin_username
  analytics_pg_admin_password = var.analytics_pg_admin_password

  behavioral_mastery_threshold = var.behavioral_mastery_threshold

  # Azure Speech Avatar configuration
  speech_region = module.speech.speech_region
  speech_key    = module.speech.speech_key

  # OIDC / SSO Configuration
  auth_mode              = var.auth_mode
  azure_ad_client_id     = var.azure_ad_client_id
  azure_ad_client_secret = var.azure_ad_client_secret
  azure_ad_tenant_id     = var.azure_ad_tenant_id
  nextauth_secret        = var.nextauth_secret
  nextauth_url           = var.nextauth_url
}

########################
# (Optional) Web App Private Endpoint
########################

resource "azurerm_private_dns_zone" "webapp" {
  count               = var.enable_app_service && var.enable_webapp_private_endpoint ? 1 : 0
  name                = "privatelink.azurewebsites.net"
  resource_group_name = azurerm_resource_group.rg.name

  tags = local.common_tags
}

resource "azurerm_private_dns_zone_virtual_network_link" "webapp_link" {
  count                 = var.enable_app_service && var.enable_webapp_private_endpoint ? 1 : 0
  name                  = "webapp-dns-link"
  resource_group_name   = azurerm_resource_group.rg.name
  private_dns_zone_name = azurerm_private_dns_zone.webapp[0].name
  virtual_network_id    = azurerm_virtual_network.vnet.id
}

resource "azurerm_private_endpoint" "webapp" {
  count               = var.enable_app_service && var.enable_webapp_private_endpoint ? 1 : 0
  name                = "pe-webapp-${var.environment}"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  subnet_id           = azurerm_subnet.subnet_private_endpoints.id

  private_service_connection {
    name                           = "psc-webapp-${var.environment}"
    private_connection_resource_id = module.app[0].web_app_id
    is_manual_connection           = false
    subresource_names              = ["sites"]
  }

  private_dns_zone_group {
    name                 = "webapp-dnszone-group"
    private_dns_zone_ids = [azurerm_private_dns_zone.webapp[0].id]
  }

  tags = local.common_tags
}

########################
# Diagnostic Settings
########################

resource "azurerm_monitor_diagnostic_setting" "diag_openai" {
  name               = "diag-openai"
  target_resource_id = module.openai.cognitive_account_id

  log_analytics_workspace_id = azurerm_log_analytics_workspace.log_analytics.id

  enabled_log {
    category = "Audit"
  }

  # Enable request/response logging if supported for Azure OpenAI
  enabled_log {
    category = "RequestResponse"
  }

  enabled_metric {
    category = "AllMetrics"
  }
}

resource "azurerm_monitor_diagnostic_setting" "diag_storage" {
  name               = "diag-storage"
  target_resource_id = azurerm_storage_account.storage.id

  log_analytics_workspace_id = azurerm_log_analytics_workspace.log_analytics.id

  enabled_metric {
    category = "AllMetrics"
  }
}

resource "azurerm_monitor_diagnostic_setting" "diag_webapp" {
  count              = var.enable_app_service ? 1 : 0
  name               = "diag-webapp"
  target_resource_id = module.app[0].web_app_id

  log_analytics_workspace_id = azurerm_log_analytics_workspace.log_analytics.id

  enabled_log {
    category = "AppServiceHTTPLogs"
  }

  enabled_log {
    category = "AppServiceConsoleLogs"
  }

  enabled_metric {
    category = "AllMetrics"
  }
}

resource "azurerm_monitor_diagnostic_setting" "diag_functionapp" {
  count              = var.enable_app_service ? 1 : 0
  name               = "diag-functionapp"
  target_resource_id = module.app[0].function_app_id

  log_analytics_workspace_id = azurerm_log_analytics_workspace.log_analytics.id

  enabled_log {
    category = "FunctionAppLogs"
  }

  enabled_metric {
    category = "AllMetrics"
  }
}

########################
# Resource address moves (root -> modules/openai & modules/app)
########################

moved {
  from = azurerm_cognitive_account.openai
  to   = module.openai.azurerm_cognitive_account.openai
}

moved {
  from = azurerm_cognitive_deployment.persona_core_chat
  to   = module.openai.azurerm_cognitive_deployment.persona_core_chat
}

moved {
  from = azurerm_cognitive_deployment.persona_high_reasoning
  to   = module.openai.azurerm_cognitive_deployment.persona_high_reasoning
}

moved {
  from = azurerm_cognitive_deployment.PULSE_audio_realtime
  to   = module.openai.azurerm_cognitive_deployment.PULSE_audio_realtime
}

moved {
  from = azurerm_cognitive_deployment.persona_visual_asset
  to   = module.openai.azurerm_cognitive_deployment.persona_visual_asset
}

moved {
  from = azurerm_service_plan.app_plan
  to   = module.app.azurerm_service_plan.app_plan
}

moved {
  from = azurerm_linux_web_app.PULSE_ui_api
  to   = module.app.azurerm_linux_web_app.PULSE_ui_api
}

moved {
  from = azurerm_app_service_virtual_network_swift_connection.PULSE_ui_api_vnet_integration
  to   = module.app.azurerm_app_service_virtual_network_swift_connection.PULSE_ui_api_vnet_integration
}

moved {
  from = azurerm_linux_function_app.scenario_orchestrator
  to   = module.app.azurerm_linux_function_app.scenario_orchestrator
}

moved {
  from = azurerm_app_service_virtual_network_swift_connection.scenario_orchestrator_vnet_integration
  to   = module.app.azurerm_app_service_virtual_network_swift_connection.scenario_orchestrator_vnet_integration
}

########################
# Locals
########################

locals {
  common_tags = {
    project        = "PULSE-H2"
    training_tier  = "H4"
    classification = "RESTRICTED"
    methodology    = "Hyper-Engineered Behavioral Sales (PULSE)"
    environment    = var.environment
    owner          = var.owner
  }
}