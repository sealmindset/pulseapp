variable "resource_group_name" {
  type        = string
  description = "Resource group for analytics PostgreSQL resources."
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
  description = "Common tags applied to analytics resources."
}

variable "virtual_network_name" {
  type        = string
  description = "Name of the existing virtual network for analytics subnet delegation."
}

variable "virtual_network_id" {
  type        = string
  description = "ID of the existing virtual network for analytics DNS link."
}

variable "analytics_pg_subnet_prefix" {
  type        = string
  description = "Address prefix for the analytics PostgreSQL subnet."
}

variable "analytics_pg_version" {
  type        = string
  description = "PostgreSQL engine version for analytics."
}

variable "analytics_pg_sku_name" {
  type        = string
  description = "SKU name for the analytics PostgreSQL flexible server."
}

variable "analytics_pg_storage_mb" {
  type        = number
  description = "Allocated storage in MB for the analytics PostgreSQL flexible server."
}

variable "analytics_pg_backup_retention_days" {
  type        = number
  description = "Backup retention in days for analytics PostgreSQL."
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

variable "network_security_group_id" {
  type        = string
  description = "ID of the NSG to associate with the PostgreSQL subnet."
  default     = null
}

variable "enable_nsg_association" {
  type        = bool
  description = "Whether to associate an NSG with the PostgreSQL subnet."
  default     = false
}
