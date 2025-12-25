locals {
  speech_account_name = "speech-${lower(var.project_name)}-${var.environment}"
}

resource "azurerm_cognitive_account" "speech" {
  count                 = var.enable_speech_avatar ? 1 : 0
  name                  = local.speech_account_name
  location              = var.location
  resource_group_name   = var.resource_group_name
  custom_subdomain_name = local.speech_account_name

  kind     = "SpeechServices"
  sku_name = var.speech_sku_name

  public_network_access_enabled = true

  tags = merge(var.common_tags, {
    service_role = "speech-avatar"
  })
}
