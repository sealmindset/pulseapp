locals {
  analytics_server_name = "pg-${var.project_name}-analytics-${var.environment}"
}

resource "azurerm_subnet" "analytics_pg" {
  name                 = "PULSE-analytics-pg-subnet"
  resource_group_name  = var.resource_group_name
  virtual_network_name = var.virtual_network_name
  address_prefixes     = [var.analytics_pg_subnet_prefix]

  delegation {
    name = "postgresql-flexible-server"

    service_delegation {
      name = "Microsoft.DBforPostgreSQL/flexibleServers"
      actions = [
        "Microsoft.Network/virtualNetworks/subnets/action",
      ]
    }
  }
}

resource "azurerm_private_dns_zone" "analytics_pg" {
  name                = "privatelink.postgres.database.azure.com"
  resource_group_name = var.resource_group_name

  tags = merge(var.common_tags, {
    service_role = "analytics-database-dns"
  })
}

resource "azurerm_private_dns_zone_virtual_network_link" "analytics_pg_link" {
  name                  = "analytics-pg-dns-link"
  resource_group_name   = var.resource_group_name
  private_dns_zone_name = azurerm_private_dns_zone.analytics_pg.name
  virtual_network_id    = var.virtual_network_id
}

resource "azurerm_postgresql_flexible_server" "analytics" {
  name                = local.analytics_server_name
  resource_group_name = var.resource_group_name
  location            = var.location

  administrator_login    = var.analytics_pg_admin_username
  administrator_password = var.analytics_pg_admin_password

  version    = var.analytics_pg_version
  storage_mb = var.analytics_pg_storage_mb
  sku_name   = var.analytics_pg_sku_name

  backup_retention_days        = var.analytics_pg_backup_retention_days
  geo_redundant_backup_enabled = false

  delegated_subnet_id = azurerm_subnet.analytics_pg.id
  private_dns_zone_id = azurerm_private_dns_zone.analytics_pg.id

  tags = merge(var.common_tags, {
    service_role = "analytics-database"
  })
}

resource "azurerm_postgresql_flexible_server_database" "analytics_db" {
  name      = "pulse_analytics"
  server_id = azurerm_postgresql_flexible_server.analytics.id
  charset   = "UTF8"
  collation = "en_US.utf8"
}
