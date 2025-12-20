output "speech_account_id" {
  description = "ID of the Azure Speech Services account."
  value       = var.enable_speech_avatar ? azurerm_cognitive_account.speech[0].id : null
}

output "speech_account_name" {
  description = "Name of the Azure Speech Services account."
  value       = var.enable_speech_avatar ? azurerm_cognitive_account.speech[0].name : null
}

output "speech_endpoint" {
  description = "Endpoint URL for Azure Speech Services."
  value       = var.enable_speech_avatar ? azurerm_cognitive_account.speech[0].endpoint : null
}

output "speech_region" {
  description = "Region for Azure Speech Services (needed for SDK)."
  value       = var.enable_speech_avatar ? var.location : null
}

output "speech_key" {
  description = "Primary API key for Azure Speech Services."
  value       = var.enable_speech_avatar ? azurerm_cognitive_account.speech[0].primary_access_key : ""
  sensitive   = true
}
