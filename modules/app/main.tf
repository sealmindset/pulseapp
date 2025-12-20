locals {
  service_plan_name = "asp-${var.project_name}-${var.environment}"
  web_app_name      = "app-${var.project_name}-ui-${var.environment}"
  function_app_name = "func-${var.project_name}-scenario-${var.environment}"
}

resource "azurerm_service_plan" "app_plan" {
  name                = local.service_plan_name
  resource_group_name = var.resource_group_name
  location            = var.location

  os_type  = "Linux"
  sku_name = var.app_service_sku_name

  tags = var.common_tags
}

resource "azurerm_linux_web_app" "PULSE_ui_api" {
  name                = local.web_app_name
  resource_group_name = var.resource_group_name
  location            = var.location
  service_plan_id     = azurerm_service_plan.app_plan.id

  https_only = true

  identity {
    type = "SystemAssigned"
  }

  site_config {
    always_on = true

    application_stack {
      node_version = "18-lts"
    }
  }

  app_settings = {
    "WEBSITE_RUN_FROM_PACKAGE"              = "0"
    "APPLICATIONINSIGHTS_CONNECTION_STRING" = var.app_insights_connection_string

    "OPENAI_ENDPOINT"                          = var.openai_endpoint
    "OPENAI_API_VERSION"                       = var.openai_api_version
    "OPENAI_DEPLOYMENT_PERSONA_CORE_CHAT"      = var.deployment_persona_core_chat_name
    "OPENAI_DEPLOYMENT_PERSONA_HIGH_REASONING" = var.deployment_persona_high_reasoning_name
    "OPENAI_DEPLOYMENT_PULSE_AUDIO_REALTIME"   = var.deployment_PULSE_audio_realtime_name
    "OPENAI_DEPLOYMENT_PERSONA_VISUAL_ASSET"   = var.deployment_persona_visual_asset_name

    "STORAGE_ACCOUNT_NAME"               = var.storage_account_name
    "STORAGE_CERTIFICATION_CONTAINER"    = var.storage_certification_container
    "STORAGE_INTERACTION_LOGS_CONTAINER" = var.storage_interaction_logs_container

    "BEHAVIORAL_MASTERY_THRESHOLD" = tostring(var.behavioral_mastery_threshold)

    "PULSE_ANALYTICS_DB_HOST"     = var.analytics_pg_fqdn
    "PULSE_ANALYTICS_DB_PORT"     = "5432"
    "PULSE_ANALYTICS_DB_NAME"     = var.analytics_pg_database_name
    "PULSE_ANALYTICS_DB_USER"     = var.analytics_pg_admin_username
    "PULSE_ANALYTICS_DB_PASSWORD" = var.analytics_pg_admin_password

    # Next.js environment variables (NEXT_PUBLIC_ are build-time, but set for reference)
    "NEXT_PUBLIC_ENABLE_ADMIN" = "true"
    "NEXT_PUBLIC_ENV_NAME"     = var.environment == "prod" ? "dev" : var.environment
    "PORT"                     = "3000"

    # Function App URL for API proxy routes
    "FUNCTION_APP_BASE_URL" = "https://${local.function_app_name}.azurewebsites.net/api"
  }

  tags = merge(var.common_tags, { service_role = "ui-api" })
}

resource "azurerm_app_service_virtual_network_swift_connection" "PULSE_ui_api_vnet_integration" {
  app_service_id = azurerm_linux_web_app.PULSE_ui_api.id
  subnet_id      = var.subnet_app_id
}

resource "azurerm_linux_function_app" "scenario_orchestrator" {
  name                = local.function_app_name
  resource_group_name = var.resource_group_name
  location            = var.location

  service_plan_id             = azurerm_service_plan.app_plan.id
  storage_account_name        = var.storage_account_name
  storage_account_access_key  = var.storage_account_primary_access_key

  https_only = true

  identity {
    type = "SystemAssigned"
  }

  site_config {
    application_stack {
      python_version = "3.11"
    }
    always_on = true
  }

  app_settings = {
    "FUNCTIONS_WORKER_RUNTIME"              = "python"
    "AzureWebJobsStorage"                   = var.storage_account_primary_connection_string
    "APPLICATIONINSIGHTS_CONNECTION_STRING" = var.app_insights_connection_string

    "OPENAI_ENDPOINT"                          = var.openai_endpoint
    "OPENAI_API_VERSION"                       = var.openai_api_version
    "AZURE_OPENAI_API_KEY"                     = var.openai_api_key
    "OPENAI_DEPLOYMENT_PERSONA_CORE_CHAT"      = var.deployment_persona_core_chat_name
    "OPENAI_DEPLOYMENT_PERSONA_HIGH_REASONING" = var.deployment_persona_high_reasoning_name
    "OPENAI_DEPLOYMENT_PULSE_AUDIO_REALTIME"   = var.deployment_PULSE_audio_realtime_name

    "STORAGE_ACCOUNT_NAME"               = var.storage_account_name
    "STORAGE_CERTIFICATION_CONTAINER"    = var.storage_certification_container
    "STORAGE_INTERACTION_LOGS_CONTAINER" = var.storage_interaction_logs_container

    "SCENARIO_PROCESS_PIPELINE"          = var.scenario_process_pipeline
    "BEHAVIORAL_MASTERY_THRESHOLD"       = tostring(var.behavioral_mastery_threshold)

    "PULSE_ANALYTICS_DB_HOST"     = var.analytics_pg_fqdn
    "PULSE_ANALYTICS_DB_PORT"     = "5432"
    "PULSE_ANALYTICS_DB_NAME"     = var.analytics_pg_database_name
    "PULSE_ANALYTICS_DB_USER"     = var.analytics_pg_admin_username
    "PULSE_ANALYTICS_DB_PASSWORD" = var.analytics_pg_admin_password

    # Azure Speech Avatar configuration
    "AZURE_SPEECH_REGION" = var.speech_region != null ? var.speech_region : var.location
    "AZURE_SPEECH_KEY"    = var.speech_key

    # Training orchestrator - enable by default for deployed environments
    "TRAINING_ORCHESTRATOR_ENABLED" = "true"
    "AUDIO_PROCESSING_ENABLED"      = "true"

    # Blob container for session data
    "PROMPTS_CONTAINER" = var.storage_interaction_logs_container

    # Enable Oryx build for Python dependencies
    "SCM_DO_BUILD_DURING_DEPLOYMENT" = "true"
    "ENABLE_ORYX_BUILD"              = "true"
  }

  tags = merge(var.common_tags, { service_role = "scenario-orchestrator" })
}

resource "azurerm_app_service_virtual_network_swift_connection" "scenario_orchestrator_vnet_integration" {
  app_service_id = azurerm_linux_function_app.scenario_orchestrator.id
  subnet_id      = var.subnet_app_id
}
