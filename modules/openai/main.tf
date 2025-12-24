locals {
  # Resource name keeps original casing
  openai_account_name = "cog-${var.project_name}-${var.environment}"
  # Subdomain must be lowercase (Azure auto-lowercases it)
  openai_subdomain    = lower("cog-${var.project_name}-${var.environment}")
}

resource "azurerm_cognitive_account" "openai" {
  name                  = local.openai_account_name
  location              = var.location
  resource_group_name   = var.resource_group_name
  custom_subdomain_name = local.openai_subdomain

  kind     = "OpenAI"
  sku_name = var.openai_sku_name

  public_network_access_enabled = var.openai_public_network_access_enabled

  tags = merge(var.common_tags, {
    service_role = "ai-engine"
  })
}

resource "azurerm_cognitive_deployment" "persona_core_chat" {
  name                 = "Persona-Core-Chat"
  cognitive_account_id = azurerm_cognitive_account.openai.id

  model {
    name    = var.openai_model_core_chat_id
    format  = "OpenAI"
    version = var.openai_model_core_chat_version
  }

  sku {
    name     = var.openai_deployment_core_chat_sku
    capacity = var.openai_deployment_core_chat_capacity
  }
}

resource "azurerm_cognitive_deployment" "persona_high_reasoning" {
  name                 = "Persona-High-Reasoning"
  cognitive_account_id = azurerm_cognitive_account.openai.id

  model {
    name    = var.openai_model_high_reasoning_id
    format  = "OpenAI"
    version = var.openai_model_high_reasoning_version
  }

  sku {
    name     = var.openai_deployment_high_reasoning_sku
    capacity = var.openai_deployment_high_reasoning_capacity
  }
}

resource "azurerm_cognitive_deployment" "PULSE_audio_realtime" {
  name                 = "PULSE-Audio-Realtime"
  cognitive_account_id = azurerm_cognitive_account.openai.id

  model {
    name    = var.openai_model_audio_realtime_id
    format  = "OpenAI"
    version = var.openai_model_audio_realtime_version
  }

  sku {
    name     = var.openai_deployment_audio_realtime_sku
    capacity = var.openai_deployment_audio_realtime_capacity
  }
}

resource "azurerm_cognitive_deployment" "persona_visual_asset" {
  count                = var.enable_visual_asset_deployment ? 1 : 0
  name                 = "Persona-Visual-Asset"
  cognitive_account_id = azurerm_cognitive_account.openai.id

  model {
    name   = var.openai_model_visual_asset_id
    format = "OpenAI"
  }

  sku {
    name     = var.openai_deployment_visual_asset_sku
    capacity = var.openai_deployment_visual_asset_capacity
  }
}

resource "azurerm_cognitive_deployment" "PULSE_whisper" {
  name                 = "PULSE-Whisper"
  cognitive_account_id = azurerm_cognitive_account.openai.id

  model {
    name    = var.openai_model_whisper_id
    format  = "OpenAI"
    version = var.openai_model_whisper_version
  }

  sku {
    name     = var.openai_deployment_whisper_sku
    capacity = var.openai_deployment_whisper_capacity
  }
}
