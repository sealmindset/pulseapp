variable "environment" {
  type        = string
  description = "Deployment environment (e.g., prod, staging)."
  default     = "prod"
}

variable "location" {
  type        = string
  description = "Azure region for all resources."
  default     = "East US 2"
}

variable "resource_group_name" {
  type        = string
  description = "Name of the Azure resource group."
  default     = "rg-PULSE-training-prod"
}

variable "project_name" {
  type        = string
  description = "Short project name used in resource naming."
  default     = "PULSE-training"
}

variable "owner" {
  type        = string
  description = "Owner or business unit for tagging."
}

variable "vnet_address_space" {
  type        = list(string)
  description = "Address space for the VNet."
  default     = ["10.10.0.0/16"]
}

variable "subnet_app_prefix" {
  type        = string
  description = "Address prefix for the application subnet."
  default     = "10.10.1.0/24"
}

variable "subnet_private_endpoints_prefix" {
  type        = string
  description = "Address prefix for the private endpoints subnet."
  default     = "10.10.2.0/24"
}

variable "app_service_sku_name" {
  type        = string
  description = "SKU name for the App Service Plan."
  default     = "P1v3"
}

variable "storage_account_name" {
  type        = string
  description = "Globally unique name for the storage account."
}

variable "openai_sku_name" {
  type        = string
  description = "SKU name for the Azure OpenAI cognitive account."
  default     = "S0"
}

variable "openai_api_version" {
  type        = string
  description = "Azure OpenAI API version to use."
  default     = "2024-10-01-preview"
}

# Model IDs and versions

variable "openai_model_core_chat_id" {
  type        = string
  description = "Model ID for Persona-Core-Chat deployment."
  default     = "gpt-5-chat"
}

variable "openai_model_core_chat_version" {
  type        = string
  description = "Model version for Persona-Core-Chat deployment."
  default     = "2025-10-03"
}

variable "openai_model_high_reasoning_id" {
  type        = string
  description = "Model ID for Persona-High-Reasoning deployment."
  default     = "o4-mini"
}

variable "openai_model_high_reasoning_version" {
  type        = string
  description = "Model version for Persona-High-Reasoning deployment."
  default     = "2025-04-16"
}

variable "openai_model_audio_realtime_id" {
  type        = string
  description = "Model ID for PULSE-Audio-Realtime deployment."
  default     = "gpt-4o-realtime-preview"
}

variable "openai_model_audio_realtime_version" {
  type        = string
  description = "Model version for PULSE-Audio-Realtime deployment."
  default     = "2024-12-17"
}

# Visual Asset (image) model
variable "openai_model_visual_asset_id" {
  type        = string
  description = "Model ID for Persona-Visual-Asset deployment (e.g., gpt-image-1 or dall-e-3)."
  default     = "gpt-image-1"
}

variable "openai_model_visual_asset_version" {
  type        = string
  description = "Model version for Persona-Visual-Asset deployment."
  default     = "2024-12-17"
}

# Deployment SKUs and capacity (abstracted for future tuning)

variable "openai_deployment_core_chat_sku" {
  type        = string
  description = "SKU name for Persona-Core-Chat deployment."
  default     = "GlobalStandard"
}

variable "openai_deployment_core_chat_capacity" {
  type        = number
  description = "Capacity for Persona-Core-Chat deployment."
  default     = 5
}

variable "openai_deployment_high_reasoning_sku" {
  type        = string
  description = "SKU name for Persona-High-Reasoning deployment."
  default     = "GlobalStandard"
}

variable "openai_deployment_high_reasoning_capacity" {
  type        = number
  description = "Capacity for Persona-High-Reasoning deployment."
  default     = 3
}

variable "openai_deployment_audio_realtime_sku" {
  type        = string
  description = "SKU name for PULSE-Audio-Realtime deployment."
  default     = "GlobalStandard"
}

variable "openai_deployment_audio_realtime_capacity" {
  type        = number
  description = "Capacity for PULSE-Audio-Realtime deployment."
  default     = 2
}

variable "openai_deployment_visual_asset_sku" {
  type        = string
  description = "SKU name for Persona-Visual-Asset deployment."
  default     = "GlobalStandard"
}

variable "openai_deployment_visual_asset_capacity" {
  type        = number
  description = "Capacity for Persona-Visual-Asset deployment."
  default     = 2
}

variable "log_analytics_retention_days" {
  type        = number
  description = "Retention in days for Log Analytics workspace."
  default     = 60
}

variable "behavioral_mastery_threshold" {
  type        = number
  description = "Threshold for Behavioral Certification mastery (0-1)."
  default     = 0.85

  validation {
    condition     = var.behavioral_mastery_threshold >= 0.85 && var.behavioral_mastery_threshold <= 1.0
    error_message = "behavioral_mastery_threshold must be between 0.85 and 1.0 inclusive."
  }
}

variable "enable_webapp_private_endpoint" {
  type        = bool
  description = "Enable private endpoint for Web App."
  default     = true
}

variable "web_app_linux_fx_version" {
  type        = string
  description = "Linux FX version string for Web App runtime (e.g. NODE|18-lts or PYTHON|3.11)."
  default     = "NODE|18-lts"
}