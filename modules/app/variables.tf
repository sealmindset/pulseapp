variable "resource_group_name" {
  type        = string
  description = "Resource group for the app resources."
}

variable "location" {
  type        = string
  description = "Azure region."
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
  description = "Common tags applied to app resources."
}

variable "app_service_sku_name" {
  type        = string
  description = "SKU name for the App Service Plan."
}

variable "web_app_linux_fx_version" {
  type        = string
  description = "Linux FX version string for Web App runtime."
}

variable "subnet_app_id" {
  type        = string
  description = "Subnet ID for app VNet integration."
}

variable "openai_endpoint" {
  type        = string
  description = "Azure OpenAI endpoint URL."
}

variable "openai_api_version" {
  type        = string
  description = "Azure OpenAI API version used by apps."
}

variable "deployment_persona_core_chat_name" {
  type        = string
  description = "Deployment name for Persona-Core-Chat."
}

variable "deployment_persona_high_reasoning_name" {
  type        = string
  description = "Deployment name for Persona-High-Reasoning."
}

variable "deployment_PULSE_audio_realtime_name" {
  type        = string
  description = "Deployment name for PULSE-Audio-Realtime."
}

variable "deployment_persona_visual_asset_name" {
  type        = string
  description = "Deployment name for Persona-Visual-Asset."
}

variable "storage_account_name" {
  type        = string
  description = "Storage account name."
}

variable "storage_account_primary_access_key" {
  type        = string
  description = "Primary access key for the storage account."
  sensitive   = true
}

variable "storage_account_primary_connection_string" {
  type        = string
  description = "Primary connection string for the storage account."
  sensitive   = true
}

variable "storage_certification_container" {
  type        = string
  description = "Name of the certification materials container."
}

variable "storage_interaction_logs_container" {
  type        = string
  description = "Name of the interaction logs container."
}

variable "app_insights_connection_string" {
  type        = string
  description = "Application Insights connection string."
}

variable "behavioral_mastery_threshold" {
  type        = number
  description = "Threshold for Behavioral Certification mastery (0-1)."
}

variable "scenario_process_pipeline" {
  type        = string
  description = "Scenario process pipeline identifier."
  default     = "PULSE-SIX-STEP"
}
