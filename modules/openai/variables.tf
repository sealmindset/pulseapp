variable "resource_group_name" {
  type        = string
  description = "Resource group for the Azure OpenAI account."
}

variable "location" {
  type        = string
  description = "Azure region for the OpenAI account."
}

variable "project_name" {
  type        = string
  description = "Short project name used in naming."
}

variable "environment" {
  type        = string
  description = "Deployment environment (e.g., prod, staging)."
}

variable "common_tags" {
  type        = map(string)
  description = "Common tags applied to all OpenAI resources."
}

variable "openai_sku_name" {
  type        = string
  description = "SKU name for the Azure OpenAI cognitive account."
}

variable "openai_model_core_chat_id" {
  type        = string
  description = "Model ID for Persona-Core-Chat deployment."
}

variable "openai_model_core_chat_version" {
  type        = string
  description = "Model version for Persona-Core-Chat deployment."
}

variable "openai_model_high_reasoning_id" {
  type        = string
  description = "Model ID for Persona-High-Reasoning deployment."
}

variable "openai_model_high_reasoning_version" {
  type        = string
  description = "Model version for Persona-High-Reasoning deployment."
}

variable "openai_model_audio_realtime_id" {
  type        = string
  description = "Model ID for PULSE-Audio-Realtime deployment."
}

variable "openai_model_audio_realtime_version" {
  type        = string
  description = "Model version for PULSE-Audio-Realtime deployment."
}

variable "openai_model_visual_asset_id" {
  type        = string
  description = "Model ID for Persona-Visual-Asset deployment."
}

variable "openai_model_visual_asset_version" {
  type        = string
  description = "Model version for Persona-Visual-Asset deployment."
}

variable "openai_deployment_core_chat_sku" {
  type        = string
  description = "SKU name for Persona-Core-Chat deployment."
}

variable "openai_deployment_core_chat_capacity" {
  type        = number
  description = "Capacity for Persona-Core-Chat deployment."
}

variable "openai_deployment_high_reasoning_sku" {
  type        = string
  description = "SKU name for Persona-High-Reasoning deployment."
}

variable "openai_deployment_high_reasoning_capacity" {
  type        = number
  description = "Capacity for Persona-High-Reasoning deployment."
}

variable "openai_deployment_audio_realtime_sku" {
  type        = string
  description = "SKU name for PULSE-Audio-Realtime deployment."
}

variable "openai_deployment_audio_realtime_capacity" {
  type        = number
  description = "Capacity for PULSE-Audio-Realtime deployment."
}

variable "openai_deployment_visual_asset_sku" {
  type        = string
  description = "SKU name for Persona-Visual-Asset deployment."
}

variable "openai_deployment_visual_asset_capacity" {
  type        = number
  description = "Capacity for Persona-Visual-Asset deployment."
}

variable "enable_visual_asset_deployment" {
  type        = bool
  description = "Whether to deploy the visual asset (DALL-E) model. Set to false if not available in subscription."
  default     = true
}

variable "openai_public_network_access_enabled" {
  type        = bool
  description = "Whether to allow public network access to the Azure OpenAI account. Set to true for testing, false for production."
  default     = false
}

# Whisper (Speech-to-Text) deployment variables
variable "openai_model_whisper_id" {
  type        = string
  description = "Model ID for PULSE-Whisper deployment (speech-to-text)."
  default     = "whisper"
}

variable "openai_model_whisper_version" {
  type        = string
  description = "Model version for PULSE-Whisper deployment."
  default     = "001"
}

variable "openai_deployment_whisper_sku" {
  type        = string
  description = "SKU name for PULSE-Whisper deployment."
  default     = "Standard"
}

variable "openai_deployment_whisper_capacity" {
  type        = number
  description = "Capacity for PULSE-Whisper deployment."
  default     = 1
}
