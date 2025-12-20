variable "project_name" {
  type        = string
  description = "Project name for resource naming."
}

variable "environment" {
  type        = string
  description = "Environment name (prod, staging, etc.)."
}

variable "location" {
  type        = string
  description = "Azure region for resources."
}

variable "resource_group_name" {
  type        = string
  description = "Resource group name."
}

variable "common_tags" {
  type        = map(string)
  description = "Common tags to apply to all resources."
  default     = {}
}

variable "enable_speech_avatar" {
  type        = bool
  description = "Whether to deploy Azure Speech Services for avatar."
  default     = true
}

variable "speech_sku_name" {
  type        = string
  description = "SKU for Azure Speech Services (S0 required for avatar)."
  default     = "S0"
}
