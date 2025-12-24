output "cognitive_account_id" {
  value       = azurerm_cognitive_account.openai.id
  description = "Resource ID of the Azure OpenAI account."
}

output "cognitive_account_name" {
  value       = azurerm_cognitive_account.openai.name
  description = "Name of the Azure OpenAI cognitive account."
}

output "endpoint" {
  value       = azurerm_cognitive_account.openai.endpoint
  description = "Endpoint URL of the Azure OpenAI account."
}

output "deployment_persona_core_chat_name" {
  value       = azurerm_cognitive_deployment.persona_core_chat.name
  description = "Deployment name for Persona-Core-Chat."
}

output "deployment_persona_high_reasoning_name" {
  value       = azurerm_cognitive_deployment.persona_high_reasoning.name
  description = "Deployment name for Persona-High-Reasoning."
}

output "deployment_PULSE_audio_realtime_name" {
  value       = azurerm_cognitive_deployment.PULSE_audio_realtime.name
  description = "Deployment name for PULSE-Audio-Realtime."
}

output "deployment_persona_visual_asset_name" {
  value       = var.enable_visual_asset_deployment ? azurerm_cognitive_deployment.persona_visual_asset[0].name : null
  description = "Deployment name for Persona-Visual-Asset."
}

output "deployment_PULSE_whisper_name" {
  value       = azurerm_cognitive_deployment.PULSE_whisper.name
  description = "Deployment name for PULSE-Whisper (speech-to-text)."
}

output "primary_key" {
  value       = azurerm_cognitive_account.openai.primary_access_key
  description = "Primary API key for Azure OpenAI."
  sensitive   = true
}
