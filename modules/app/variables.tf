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

variable "openai_api_key" {
  type        = string
  description = "Azure OpenAI API key."
  sensitive   = true
  default     = ""
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

variable "analytics_pg_fqdn" {
  type        = string
  description = "FQDN of the analytics PostgreSQL flexible server."
}

variable "analytics_pg_database_name" {
  type        = string
  description = "Name of the analytics PostgreSQL database."
}

variable "analytics_pg_admin_username" {
  type        = string
  description = "Administrator username for the analytics PostgreSQL flexible server."
}

variable "analytics_pg_admin_password" {
  type        = string
  description = "Administrator password for the analytics PostgreSQL flexible server."
  sensitive   = true
}

variable "speech_region" {
  type        = string
  description = "Azure region for Speech Services (used for avatar)."
  default     = null
}

variable "speech_key" {
  type        = string
  description = "Azure Speech Services API key for avatar."
  sensitive   = true
  default     = ""
}

# OIDC / SSO Configuration
variable "auth_mode" {
  type        = string
  description = "Authentication mode: 'demo' or 'sso'."
  default     = "demo"
}

variable "azure_ad_client_id" {
  type        = string
  description = "Microsoft Entra ID application client ID."
  default     = ""
}

variable "azure_ad_client_secret" {
  type        = string
  description = "Microsoft Entra ID application client secret."
  sensitive   = true
  default     = ""
}

variable "azure_ad_tenant_id" {
  type        = string
  description = "Microsoft Entra ID tenant ID."
  default     = ""
}

variable "nextauth_secret" {
  type        = string
  description = "Secret for NextAuth.js session encryption."
  sensitive   = true
  default     = ""
}

variable "nextauth_url" {
  type        = string
  description = "The canonical URL of the PULSE application."
  default     = ""
}
