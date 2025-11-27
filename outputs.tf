output "resource_group_name" {
  description = "Name of the resource group."
  value       = azurerm_resource_group.rg.name
}

output "location" {
  description = "Azure region used for the deployment."
  value       = azurerm_resource_group.rg.location
}

output "web_app_name" {
  description = "Name of the PULSE UI/API Web App."
  value       = module.app.web_app_name
}

output "web_app_default_hostname" {
  description = "Default hostname of the PULSE UI/API Web App."
  value       = module.app.web_app_default_hostname
}

output "function_app_name" {
  description = "Name of the Scenario Orchestrator Function App."
  value       = module.app.function_app_name
}

output "function_app_default_hostname" {
  description = "Default hostname of the Scenario Orchestrator Function App."
  value       = module.app.function_app_default_hostname
}

output "storage_account_name" {
  description = "Name of the storage account."
  value       = azurerm_storage_account.storage.name
}

output "certification_materials_container" {
  description = "Name of the certification materials container."
  value       = azurerm_storage_container.certification_materials.name
}

output "interaction_logs_container" {
  description = "Name of the interaction logs container."
  value       = azurerm_storage_container.interaction_logs.name
}

output "openai_account_name" {
  description = "Name of the Azure OpenAI cognitive account."
  value       = module.openai.cognitive_account_name
}

output "openai_endpoint" {
  description = "Endpoint of the Azure OpenAI cognitive account."
  value       = module.openai.endpoint
}

output "log_analytics_workspace_id" {
  description = "ID of the Log Analytics workspace."
  value       = azurerm_log_analytics_workspace.log_analytics.id
}

output "app_insights_connection_string" {
  description = "Application Insights connection string."
  value       = azurerm_application_insights.app_insights.connection_string
}