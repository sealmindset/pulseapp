output "service_plan_id" {
  value       = azurerm_service_plan.app_plan.id
  description = "ID of the App Service Plan."
}

output "web_app_name" {
  value       = azurerm_linux_web_app.PULSE_ui_api.name
  description = "Name of the Web App."
}

output "web_app_id" {
  value       = azurerm_linux_web_app.PULSE_ui_api.id
  description = "ID of the Web App."
}

output "web_app_default_hostname" {
  value       = azurerm_linux_web_app.PULSE_ui_api.default_hostname
  description = "Default hostname of the Web App."
}

output "function_app_id" {
  value       = azurerm_linux_function_app.scenario_orchestrator.id
  description = "ID of the Function App."
}

output "function_app_default_hostname" {
  value       = azurerm_linux_function_app.scenario_orchestrator.default_hostname
  description = "Default hostname of the Function App."
}

output "function_app_name" {
  value       = azurerm_linux_function_app.scenario_orchestrator.name
  description = "Name of the Function App."
}

