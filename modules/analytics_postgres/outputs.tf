output "analytics_pg_fqdn" {
  description = "FQDN of the analytics PostgreSQL flexible server."
  value       = azurerm_postgresql_flexible_server.analytics.fqdn
}

output "analytics_pg_database_name" {
  description = "Name of the analytics PostgreSQL database."
  value       = azurerm_postgresql_flexible_server_database.analytics_db.name
}
