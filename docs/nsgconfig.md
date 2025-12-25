# PULSE Network Security Groups (NSG) Implementation Guide

**Version:** 1.0
**Last Updated:** 2025-12-25
**Priority:** HIGH
**Related Documents:** [securedbydesign.md](securedbydesign.md), [settofalse.md](settofalse.md), [wafconfig.md](wafconfig.md)

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [NSG Architecture Overview](#nsg-architecture-overview)
3. [Current State Assessment](#current-state-assessment)
4. [Subnet and NSG Design](#subnet-and-nsg-design)
5. [NSG Rule Implementation](#nsg-rule-implementation)
6. [Application Security Groups (ASGs)](#application-security-groups-asgs)
7. [Private Endpoint NSG Rules](#private-endpoint-nsg-rules)
8. [Terraform Implementation](#terraform-implementation)
9. [NSG Flow Logs and Monitoring](#nsg-flow-logs-and-monitoring)
10. [Testing and Validation](#testing-and-validation)
11. [Migration Checklist](#migration-checklist)

---

## Executive Summary

Network Security Groups (NSGs) provide essential network-layer security for Azure resources. This guide implements comprehensive NSG rules for the PULSE application to:

- **Restrict inbound traffic** to only necessary ports and sources
- **Control outbound traffic** to prevent data exfiltration
- **Segment networks** between application tiers
- **Enable monitoring** through NSG flow logs
- **Protect Private Endpoints** with appropriate rules

---

## NSG Architecture Overview

### Multi-Layer Network Security

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           Internet                                       │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │
                    ┌───────────▼───────────┐
                    │   Azure Front Door    │
                    │   (DDoS Protection)   │
                    └───────────┬───────────┘
                                │
            ┌───────────────────▼───────────────────┐
            │            WAF Policy                  │
            │    (Layer 7 Filtering)                 │
            └───────────────────┬───────────────────┘
                                │
┌───────────────────────────────▼───────────────────────────────────────────┐
│                         Virtual Network                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                    NSG: nsg-web-subnet                               │  │
│  │  ┌─────────────────────────────────────────────────────────────┐    │  │
│  │  │              Web Subnet (10.0.1.0/24)                        │    │  │
│  │  │   ┌───────────────┐  ┌───────────────┐                       │    │  │
│  │  │   │  App Service  │  │  App Service  │                       │    │  │
│  │  │   │   (Web UI)    │  │   (API)       │                       │    │  │
│  │  │   └───────────────┘  └───────────────┘                       │    │  │
│  │  └─────────────────────────────────────────────────────────────┘    │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                    │                                       │
│  ┌─────────────────────────────────▼───────────────────────────────────┐  │
│  │                    NSG: nsg-func-subnet                              │  │
│  │  ┌─────────────────────────────────────────────────────────────┐    │  │
│  │  │              Function Subnet (10.0.2.0/24)                   │    │  │
│  │  │   ┌───────────────────────────────────────────────────┐      │    │  │
│  │  │   │              Function App                          │      │    │  │
│  │  │   └───────────────────────────────────────────────────┘      │    │  │
│  │  └─────────────────────────────────────────────────────────────┘    │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                    │                                       │
│  ┌─────────────────────────────────▼───────────────────────────────────┐  │
│  │                    NSG: nsg-pe-subnet                                │  │
│  │  ┌─────────────────────────────────────────────────────────────┐    │  │
│  │  │           Private Endpoint Subnet (10.0.3.0/24)              │    │  │
│  │  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐            │    │  │
│  │  │  │ PE:AOAI │ │PE:Storage│ │PE:Postgres│ │PE:KeyVault│        │    │  │
│  │  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘            │    │  │
│  │  └─────────────────────────────────────────────────────────────┘    │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────────────┘
```

### NSG Best Practices

| Practice | Description |
|----------|-------------|
| Least Privilege | Only allow necessary traffic |
| Deny by Default | Explicit allow rules only |
| Subnet-level NSGs | Apply NSGs to subnets, not individual resources |
| ASG Usage | Use Application Security Groups for logical grouping |
| Flow Logs | Enable for visibility and compliance |
| Rule Documentation | Use descriptions for all rules |

---

## Current State Assessment

### Potential Current Gaps

Without proper NSG configuration, the PULSE infrastructure may have:

1. **No inbound traffic filtering** - All traffic allowed to subnets
2. **No outbound restrictions** - Potential data exfiltration risk
3. **No network segmentation** - All resources can communicate freely
4. **No traffic visibility** - No flow logs for analysis
5. **Private Endpoints unprotected** - No NSG rules on PE subnets

### Required NSG Associations

| Subnet | Purpose | NSG Required |
|--------|---------|--------------|
| web-subnet | App Service VNet Integration | Yes |
| func-subnet | Function App VNet Integration | Yes |
| pe-subnet | Private Endpoints | Yes |
| bastion-subnet | Azure Bastion (if used) | Special rules |

---

## Subnet and NSG Design

### Recommended Subnet Allocation

```hcl
# Network address space: 10.0.0.0/16

subnets = {
  web = {
    name             = "snet-web"
    address_prefixes = ["10.0.1.0/24"]
    nsg_name         = "nsg-web"
    service_endpoints = ["Microsoft.Web"]
  }
  func = {
    name             = "snet-func"
    address_prefixes = ["10.0.2.0/24"]
    nsg_name         = "nsg-func"
    service_endpoints = ["Microsoft.Web"]
  }
  private_endpoints = {
    name             = "snet-pe"
    address_prefixes = ["10.0.3.0/24"]
    nsg_name         = "nsg-pe"
    private_endpoint_network_policies = "Enabled"
  }
  bastion = {
    name             = "AzureBastionSubnet"
    address_prefixes = ["10.0.4.0/27"]
    nsg_name         = "nsg-bastion"
  }
}
```

---

## NSG Rule Implementation

### Web Subnet NSG Rules

```hcl
# NSG for Web Application Subnet

# Inbound Rules
inbound_rules = [
  {
    name                       = "AllowAzureFrontDoor"
    priority                   = 100
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "443"
    source_address_prefix      = "AzureFrontDoor.Backend"
    destination_address_prefix = "VirtualNetwork"
    description                = "Allow HTTPS from Azure Front Door"
  },
  {
    name                       = "AllowAzureLoadBalancer"
    priority                   = 110
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "*"
    source_port_range          = "*"
    destination_port_range     = "*"
    source_address_prefix      = "AzureLoadBalancer"
    destination_address_prefix = "*"
    description                = "Allow Azure Load Balancer health probes"
  },
  {
    name                       = "AllowVNetInbound"
    priority                   = 120
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "*"
    source_port_range          = "*"
    destination_port_range     = "*"
    source_address_prefix      = "VirtualNetwork"
    destination_address_prefix = "VirtualNetwork"
    description                = "Allow intra-VNet traffic"
  },
  {
    name                       = "DenyAllInbound"
    priority                   = 4096
    direction                  = "Inbound"
    access                     = "Deny"
    protocol                   = "*"
    source_port_range          = "*"
    destination_port_range     = "*"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
    description                = "Deny all other inbound traffic"
  }
]

# Outbound Rules
outbound_rules = [
  {
    name                       = "AllowPrivateEndpoints"
    priority                   = 100
    direction                  = "Outbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "443"
    source_address_prefix      = "VirtualNetwork"
    destination_address_prefix = "10.0.3.0/24"  # PE subnet
    description                = "Allow HTTPS to Private Endpoints"
  },
  {
    name                       = "AllowAzureMonitor"
    priority                   = 110
    direction                  = "Outbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "443"
    source_address_prefix      = "VirtualNetwork"
    destination_address_prefix = "AzureMonitor"
    description                = "Allow Azure Monitor telemetry"
  },
  {
    name                       = "AllowAzureActiveDirectory"
    priority                   = 120
    direction                  = "Outbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "443"
    source_address_prefix      = "VirtualNetwork"
    destination_address_prefix = "AzureActiveDirectory"
    description                = "Allow Azure AD authentication"
  },
  {
    name                       = "AllowDNS"
    priority                   = 130
    direction                  = "Outbound"
    access                     = "Allow"
    protocol                   = "*"
    source_port_range          = "*"
    destination_port_range     = "53"
    source_address_prefix      = "VirtualNetwork"
    destination_address_prefix = "*"
    description                = "Allow DNS resolution"
  },
  {
    name                       = "DenyInternetOutbound"
    priority                   = 4000
    direction                  = "Outbound"
    access                     = "Deny"
    protocol                   = "*"
    source_port_range          = "*"
    destination_port_range     = "*"
    source_address_prefix      = "VirtualNetwork"
    destination_address_prefix = "Internet"
    description                = "Deny direct internet access"
  }
]
```

### Function App Subnet NSG Rules

```hcl
# NSG for Function App Subnet

inbound_rules = [
  {
    name                       = "AllowWebSubnet"
    priority                   = 100
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "443"
    source_address_prefix      = "10.0.1.0/24"  # Web subnet
    destination_address_prefix = "VirtualNetwork"
    description                = "Allow HTTPS from Web subnet"
  },
  {
    name                       = "AllowAzureLoadBalancer"
    priority                   = 110
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "*"
    source_port_range          = "*"
    destination_port_range     = "*"
    source_address_prefix      = "AzureLoadBalancer"
    destination_address_prefix = "*"
    description                = "Allow Azure Load Balancer health probes"
  },
  {
    name                       = "DenyAllInbound"
    priority                   = 4096
    direction                  = "Inbound"
    access                     = "Deny"
    protocol                   = "*"
    source_port_range          = "*"
    destination_port_range     = "*"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
    description                = "Deny all other inbound traffic"
  }
]

outbound_rules = [
  {
    name                       = "AllowPrivateEndpoints"
    priority                   = 100
    direction                  = "Outbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "443"
    source_address_prefix      = "VirtualNetwork"
    destination_address_prefix = "10.0.3.0/24"
    description                = "Allow HTTPS to Private Endpoints"
  },
  {
    name                       = "AllowPostgres"
    priority                   = 110
    direction                  = "Outbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "5432"
    source_address_prefix      = "VirtualNetwork"
    destination_address_prefix = "10.0.3.0/24"
    description                = "Allow PostgreSQL to Private Endpoint"
  },
  {
    name                       = "AllowAzureServices"
    priority                   = 120
    direction                  = "Outbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "443"
    source_address_prefix      = "VirtualNetwork"
    destination_address_prefix = "AzureCloud"
    description                = "Allow Azure management services"
  },
  {
    name                       = "DenyInternetOutbound"
    priority                   = 4000
    direction                  = "Outbound"
    access                     = "Deny"
    protocol                   = "*"
    source_port_range          = "*"
    destination_port_range     = "*"
    source_address_prefix      = "VirtualNetwork"
    destination_address_prefix = "Internet"
    description                = "Deny direct internet access"
  }
]
```

### Private Endpoint Subnet NSG Rules

```hcl
# NSG for Private Endpoint Subnet

inbound_rules = [
  {
    name                       = "AllowWebSubnetHTTPS"
    priority                   = 100
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "443"
    source_address_prefix      = "10.0.1.0/24"
    destination_address_prefix = "VirtualNetwork"
    description                = "Allow HTTPS from Web subnet"
  },
  {
    name                       = "AllowFuncSubnetHTTPS"
    priority                   = 110
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "443"
    source_address_prefix      = "10.0.2.0/24"
    destination_address_prefix = "VirtualNetwork"
    description                = "Allow HTTPS from Function subnet"
  },
  {
    name                       = "AllowFuncSubnetPostgres"
    priority                   = 120
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "5432"
    source_address_prefix      = "10.0.2.0/24"
    destination_address_prefix = "VirtualNetwork"
    description                = "Allow PostgreSQL from Function subnet"
  },
  {
    name                       = "DenyAllInbound"
    priority                   = 4096
    direction                  = "Inbound"
    access                     = "Deny"
    protocol                   = "*"
    source_port_range          = "*"
    destination_port_range     = "*"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
    description                = "Deny all other inbound traffic"
  }
]

# Private Endpoints don't initiate outbound connections
outbound_rules = [
  {
    name                       = "DenyAllOutbound"
    priority                   = 4096
    direction                  = "Outbound"
    access                     = "Deny"
    protocol                   = "*"
    source_port_range          = "*"
    destination_port_range     = "*"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
    description                = "Private Endpoints don't need outbound access"
  }
]
```

---

## Application Security Groups (ASGs)

### ASG Design

Application Security Groups provide logical grouping for network security rules.

```hcl
# Application Security Groups

asgs = {
  web_apps = {
    name = "asg-web-apps"
    description = "Web application tier"
  }
  function_apps = {
    name = "asg-function-apps"
    description = "Function app tier"
  }
  private_endpoints = {
    name = "asg-private-endpoints"
    description = "Private endpoint resources"
  }
  databases = {
    name = "asg-databases"
    description = "Database resources"
  }
}
```

### ASG-Based NSG Rules

```hcl
# NSG rules using ASGs for more flexible management

resource "azurerm_network_security_rule" "web_to_function" {
  name                                       = "AllowWebToFunction"
  priority                                   = 100
  direction                                  = "Inbound"
  access                                     = "Allow"
  protocol                                   = "Tcp"
  source_port_range                          = "*"
  destination_port_range                     = "443"
  source_application_security_group_ids      = [azurerm_application_security_group.web_apps.id]
  destination_application_security_group_ids = [azurerm_application_security_group.function_apps.id]
  resource_group_name                        = var.resource_group_name
  network_security_group_name                = azurerm_network_security_group.func.name
  description                                = "Allow web apps to call function apps"
}

resource "azurerm_network_security_rule" "function_to_database" {
  name                                       = "AllowFunctionToDatabase"
  priority                                   = 100
  direction                                  = "Inbound"
  access                                     = "Allow"
  protocol                                   = "Tcp"
  source_port_range                          = "*"
  destination_port_range                     = "5432"
  source_application_security_group_ids      = [azurerm_application_security_group.function_apps.id]
  destination_application_security_group_ids = [azurerm_application_security_group.databases.id]
  resource_group_name                        = var.resource_group_name
  network_security_group_name                = azurerm_network_security_group.pe.name
  description                                = "Allow function apps to access PostgreSQL"
}
```

---

## Private Endpoint NSG Rules

### Enable NSG for Private Endpoints

By default, NSG rules don't apply to Private Endpoints. Enable this feature:

```hcl
# Enable NSG enforcement on Private Endpoint subnet
resource "azurerm_subnet" "private_endpoints" {
  name                 = "snet-pe"
  resource_group_name  = var.resource_group_name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = ["10.0.3.0/24"]

  # Enable NSG support for Private Endpoints
  private_endpoint_network_policies = "Enabled"
}
```

### Service-Specific Private Endpoint Rules

```hcl
# Rules for specific Private Endpoint services

# Azure OpenAI Private Endpoint
resource "azurerm_network_security_rule" "allow_openai_pe" {
  name                        = "AllowOpenAI"
  priority                    = 100
  direction                   = "Inbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = "443"
  source_address_prefixes     = ["10.0.1.0/24", "10.0.2.0/24"]  # Web + Func
  destination_address_prefix  = azurerm_private_endpoint.openai.private_service_connection[0].private_ip_address
  resource_group_name         = var.resource_group_name
  network_security_group_name = azurerm_network_security_group.pe.name
  description                 = "Allow access to Azure OpenAI Private Endpoint"
}

# Azure Storage Private Endpoint
resource "azurerm_network_security_rule" "allow_storage_pe" {
  name                        = "AllowStorage"
  priority                    = 110
  direction                   = "Inbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = "443"
  source_address_prefixes     = ["10.0.1.0/24", "10.0.2.0/24"]
  destination_address_prefix  = azurerm_private_endpoint.storage.private_service_connection[0].private_ip_address
  resource_group_name         = var.resource_group_name
  network_security_group_name = azurerm_network_security_group.pe.name
  description                 = "Allow access to Storage Private Endpoint"
}

# PostgreSQL Private Endpoint
resource "azurerm_network_security_rule" "allow_postgres_pe" {
  name                        = "AllowPostgres"
  priority                    = 120
  direction                   = "Inbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = "5432"
  source_address_prefix       = "10.0.2.0/24"  # Only Function subnet
  destination_address_prefix  = azurerm_private_endpoint.postgres.private_service_connection[0].private_ip_address
  resource_group_name         = var.resource_group_name
  network_security_group_name = azurerm_network_security_group.pe.name
  description                 = "Allow access to PostgreSQL Private Endpoint"
}

# Key Vault Private Endpoint
resource "azurerm_network_security_rule" "allow_keyvault_pe" {
  name                        = "AllowKeyVault"
  priority                    = 130
  direction                   = "Inbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = "443"
  source_address_prefixes     = ["10.0.1.0/24", "10.0.2.0/24"]
  destination_address_prefix  = azurerm_private_endpoint.keyvault.private_service_connection[0].private_ip_address
  resource_group_name         = var.resource_group_name
  network_security_group_name = azurerm_network_security_group.pe.name
  description                 = "Allow access to Key Vault Private Endpoint"
}
```

---

## Terraform Implementation

### Complete NSG Module

Create `infra/modules/nsg/main.tf`:

```hcl
# Network Security Group Module

terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
}

# Variables
variable "resource_group_name" {
  type        = string
  description = "Resource group name"
}

variable "location" {
  type        = string
  description = "Azure region"
}

variable "environment" {
  type        = string
  description = "Environment (dev, staging, prod)"
}

variable "vnet_address_space" {
  type        = list(string)
  description = "VNet address space"
  default     = ["10.0.0.0/16"]
}

variable "subnets" {
  type = map(object({
    address_prefixes = list(string)
    service_endpoints = optional(list(string), [])
    private_endpoint_network_policies = optional(string, "Disabled")
  }))
  description = "Subnet configurations"
}

variable "tags" {
  type        = map(string)
  description = "Resource tags"
  default     = {}
}

# Local values
locals {
  nsg_configs = {
    web = {
      name = "nsg-web-${var.environment}"
      inbound_rules = [
        {
          name                       = "AllowFrontDoor"
          priority                   = 100
          direction                  = "Inbound"
          access                     = "Allow"
          protocol                   = "Tcp"
          source_port_range          = "*"
          destination_port_range     = "443"
          source_address_prefix      = "AzureFrontDoor.Backend"
          destination_address_prefix = "VirtualNetwork"
          description                = "Allow Azure Front Door"
        },
        {
          name                       = "AllowHealthProbes"
          priority                   = 110
          direction                  = "Inbound"
          access                     = "Allow"
          protocol                   = "*"
          source_port_range          = "*"
          destination_port_range     = "*"
          source_address_prefix      = "AzureLoadBalancer"
          destination_address_prefix = "*"
          description                = "Allow health probes"
        },
        {
          name                       = "AllowVNet"
          priority                   = 120
          direction                  = "Inbound"
          access                     = "Allow"
          protocol                   = "*"
          source_port_range          = "*"
          destination_port_range     = "*"
          source_address_prefix      = "VirtualNetwork"
          destination_address_prefix = "VirtualNetwork"
          description                = "Allow VNet traffic"
        },
        {
          name                       = "DenyAll"
          priority                   = 4096
          direction                  = "Inbound"
          access                     = "Deny"
          protocol                   = "*"
          source_port_range          = "*"
          destination_port_range     = "*"
          source_address_prefix      = "*"
          destination_address_prefix = "*"
          description                = "Deny all inbound"
        }
      ]
      outbound_rules = [
        {
          name                       = "AllowPE"
          priority                   = 100
          direction                  = "Outbound"
          access                     = "Allow"
          protocol                   = "Tcp"
          source_port_range          = "*"
          destination_port_range     = "443"
          source_address_prefix      = "VirtualNetwork"
          destination_address_prefix = var.subnets["pe"].address_prefixes[0]
          description                = "Allow PE access"
        },
        {
          name                       = "AllowAzureServices"
          priority                   = 110
          direction                  = "Outbound"
          access                     = "Allow"
          protocol                   = "Tcp"
          source_port_range          = "*"
          destination_port_range     = "443"
          source_address_prefix      = "VirtualNetwork"
          destination_address_prefix = "AzureCloud"
          description                = "Allow Azure services"
        },
        {
          name                       = "AllowDNS"
          priority                   = 120
          direction                  = "Outbound"
          access                     = "Allow"
          protocol                   = "*"
          source_port_range          = "*"
          destination_port_range     = "53"
          source_address_prefix      = "VirtualNetwork"
          destination_address_prefix = "*"
          description                = "Allow DNS"
        },
        {
          name                       = "DenyInternet"
          priority                   = 4000
          direction                  = "Outbound"
          access                     = "Deny"
          protocol                   = "*"
          source_port_range          = "*"
          destination_port_range     = "*"
          source_address_prefix      = "VirtualNetwork"
          destination_address_prefix = "Internet"
          description                = "Deny internet"
        }
      ]
    }
    func = {
      name = "nsg-func-${var.environment}"
      inbound_rules = [
        {
          name                       = "AllowWebSubnet"
          priority                   = 100
          direction                  = "Inbound"
          access                     = "Allow"
          protocol                   = "Tcp"
          source_port_range          = "*"
          destination_port_range     = "443"
          source_address_prefix      = var.subnets["web"].address_prefixes[0]
          destination_address_prefix = "VirtualNetwork"
          description                = "Allow web subnet"
        },
        {
          name                       = "AllowHealthProbes"
          priority                   = 110
          direction                  = "Inbound"
          access                     = "Allow"
          protocol                   = "*"
          source_port_range          = "*"
          destination_port_range     = "*"
          source_address_prefix      = "AzureLoadBalancer"
          destination_address_prefix = "*"
          description                = "Allow health probes"
        },
        {
          name                       = "DenyAll"
          priority                   = 4096
          direction                  = "Inbound"
          access                     = "Deny"
          protocol                   = "*"
          source_port_range          = "*"
          destination_port_range     = "*"
          source_address_prefix      = "*"
          destination_address_prefix = "*"
          description                = "Deny all inbound"
        }
      ]
      outbound_rules = [
        {
          name                       = "AllowPE"
          priority                   = 100
          direction                  = "Outbound"
          access                     = "Allow"
          protocol                   = "Tcp"
          source_port_range          = "*"
          destination_port_ranges    = ["443", "5432"]
          source_address_prefix      = "VirtualNetwork"
          destination_address_prefix = var.subnets["pe"].address_prefixes[0]
          description                = "Allow PE access"
        },
        {
          name                       = "AllowAzureServices"
          priority                   = 110
          direction                  = "Outbound"
          access                     = "Allow"
          protocol                   = "Tcp"
          source_port_range          = "*"
          destination_port_range     = "443"
          source_address_prefix      = "VirtualNetwork"
          destination_address_prefix = "AzureCloud"
          description                = "Allow Azure services"
        },
        {
          name                       = "DenyInternet"
          priority                   = 4000
          direction                  = "Outbound"
          access                     = "Deny"
          protocol                   = "*"
          source_port_range          = "*"
          destination_port_range     = "*"
          source_address_prefix      = "VirtualNetwork"
          destination_address_prefix = "Internet"
          description                = "Deny internet"
        }
      ]
    }
    pe = {
      name = "nsg-pe-${var.environment}"
      inbound_rules = [
        {
          name                       = "AllowAppSubnets"
          priority                   = 100
          direction                  = "Inbound"
          access                     = "Allow"
          protocol                   = "Tcp"
          source_port_range          = "*"
          destination_port_ranges    = ["443", "5432"]
          source_address_prefixes    = [
            var.subnets["web"].address_prefixes[0],
            var.subnets["func"].address_prefixes[0]
          ]
          destination_address_prefix = "VirtualNetwork"
          description                = "Allow app subnets"
        },
        {
          name                       = "DenyAll"
          priority                   = 4096
          direction                  = "Inbound"
          access                     = "Deny"
          protocol                   = "*"
          source_port_range          = "*"
          destination_port_range     = "*"
          source_address_prefix      = "*"
          destination_address_prefix = "*"
          description                = "Deny all inbound"
        }
      ]
      outbound_rules = [
        {
          name                       = "DenyAll"
          priority                   = 4096
          direction                  = "Outbound"
          access                     = "Deny"
          protocol                   = "*"
          source_port_range          = "*"
          destination_port_range     = "*"
          source_address_prefix      = "*"
          destination_address_prefix = "*"
          description                = "Deny all outbound"
        }
      ]
    }
  }
}

# Create Network Security Groups
resource "azurerm_network_security_group" "main" {
  for_each = local.nsg_configs

  name                = each.value.name
  location            = var.location
  resource_group_name = var.resource_group_name

  tags = merge(var.tags, {
    purpose = "Network security for ${each.key} subnet"
  })
}

# Create NSG Rules
resource "azurerm_network_security_rule" "inbound" {
  for_each = {
    for rule in flatten([
      for nsg_key, nsg in local.nsg_configs : [
        for rule in nsg.inbound_rules : {
          nsg_key = nsg_key
          rule    = rule
        }
      ]
    ]) : "${rule.nsg_key}-${rule.rule.name}" => rule
  }

  name                         = each.value.rule.name
  priority                     = each.value.rule.priority
  direction                    = each.value.rule.direction
  access                       = each.value.rule.access
  protocol                     = each.value.rule.protocol
  source_port_range            = each.value.rule.source_port_range
  destination_port_range       = lookup(each.value.rule, "destination_port_range", null)
  destination_port_ranges      = lookup(each.value.rule, "destination_port_ranges", null)
  source_address_prefix        = lookup(each.value.rule, "source_address_prefix", null)
  source_address_prefixes      = lookup(each.value.rule, "source_address_prefixes", null)
  destination_address_prefix   = lookup(each.value.rule, "destination_address_prefix", null)
  resource_group_name          = var.resource_group_name
  network_security_group_name  = azurerm_network_security_group.main[each.value.nsg_key].name
  description                  = each.value.rule.description
}

resource "azurerm_network_security_rule" "outbound" {
  for_each = {
    for rule in flatten([
      for nsg_key, nsg in local.nsg_configs : [
        for rule in nsg.outbound_rules : {
          nsg_key = nsg_key
          rule    = rule
        }
      ]
    ]) : "${rule.nsg_key}-${rule.rule.name}" => rule
  }

  name                         = each.value.rule.name
  priority                     = each.value.rule.priority
  direction                    = each.value.rule.direction
  access                       = each.value.rule.access
  protocol                     = each.value.rule.protocol
  source_port_range            = each.value.rule.source_port_range
  destination_port_range       = lookup(each.value.rule, "destination_port_range", null)
  destination_port_ranges      = lookup(each.value.rule, "destination_port_ranges", null)
  source_address_prefix        = lookup(each.value.rule, "source_address_prefix", null)
  destination_address_prefix   = lookup(each.value.rule, "destination_address_prefix", null)
  resource_group_name          = var.resource_group_name
  network_security_group_name  = azurerm_network_security_group.main[each.value.nsg_key].name
  description                  = each.value.rule.description
}

# Outputs
output "nsg_ids" {
  value = {
    for key, nsg in azurerm_network_security_group.main : key => nsg.id
  }
  description = "NSG resource IDs"
}

output "nsg_names" {
  value = {
    for key, nsg in azurerm_network_security_group.main : key => nsg.name
  }
  description = "NSG names"
}
```

### NSG Flow Logs Module

Create `infra/modules/nsg/flow-logs.tf`:

```hcl
# NSG Flow Logs for traffic analysis

# Storage account for flow logs
resource "azurerm_storage_account" "flow_logs" {
  name                     = "stflowlogs${var.environment}${random_string.suffix.result}"
  resource_group_name      = var.resource_group_name
  location                 = var.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  min_tls_version          = "TLS1_2"

  tags = var.tags
}

resource "random_string" "suffix" {
  length  = 6
  special = false
  upper   = false
}

# Network Watcher (required for flow logs)
data "azurerm_network_watcher" "main" {
  name                = "NetworkWatcher_${var.location}"
  resource_group_name = "NetworkWatcherRG"
}

# Flow logs for each NSG
resource "azurerm_network_watcher_flow_log" "main" {
  for_each = azurerm_network_security_group.main

  network_watcher_name = data.azurerm_network_watcher.main.name
  resource_group_name  = data.azurerm_network_watcher.main.resource_group_name
  name                 = "flowlog-${each.value.name}"

  network_security_group_id = each.value.id
  storage_account_id        = azurerm_storage_account.flow_logs.id
  enabled                   = true
  version                   = 2

  retention_policy {
    enabled = true
    days    = 30
  }

  traffic_analytics {
    enabled               = true
    workspace_id          = var.log_analytics_workspace_id
    workspace_region      = var.location
    workspace_resource_id = var.log_analytics_workspace_resource_id
    interval_in_minutes   = 10
  }

  tags = var.tags
}
```

---

## NSG Flow Logs and Monitoring

### Traffic Analytics Queries

Create `infra/monitoring/nsg-queries.kql`:

```kql
// NSG Flow Log Analysis Queries

// 1. Top blocked traffic sources
AzureNetworkAnalytics_CL
| where TimeGenerated > ago(24h)
| where FlowStatus_s == "D"  // Denied
| summarize
    blocked_flows = count(),
    bytes = sum(toint(InboundBytes_d) + toint(OutboundBytes_d))
    by SrcIP_s
| order by blocked_flows desc
| take 20

// 2. Traffic flow by subnet
AzureNetworkAnalytics_CL
| where TimeGenerated > ago(24h)
| where FlowStatus_s == "A"  // Allowed
| summarize
    flows = count(),
    total_bytes = sum(toint(InboundBytes_d) + toint(OutboundBytes_d))
    by Subnet1_s, Subnet2_s
| order by flows desc

// 3. Denied traffic patterns
AzureNetworkAnalytics_CL
| where TimeGenerated > ago(24h)
| where FlowStatus_s == "D"
| summarize count() by bin(TimeGenerated, 1h), DestPort_d
| render timechart

// 4. Cross-subnet communication
AzureNetworkAnalytics_CL
| where TimeGenerated > ago(7d)
| where Subnet1_s != Subnet2_s
| summarize
    flows = count(),
    avg_bytes = avg(toint(InboundBytes_d) + toint(OutboundBytes_d))
    by Subnet1_s, Subnet2_s
| order by flows desc

// 5. Suspicious port scanning detection
AzureNetworkAnalytics_CL
| where TimeGenerated > ago(1h)
| where FlowStatus_s == "D"
| summarize
    unique_ports = dcount(DestPort_d),
    blocked_attempts = count()
    by SrcIP_s
| where unique_ports > 10
| order by unique_ports desc

// 6. Private Endpoint traffic
AzureNetworkAnalytics_CL
| where TimeGenerated > ago(24h)
| where Subnet2_s contains "pe" or Subnet2_s contains "private"
| summarize
    flows = count(),
    total_bytes = sum(toint(InboundBytes_d))
    by SrcIP_s, DestPort_d
| order by flows desc
```

### Alert Rules

Create `infra/modules/monitoring/nsg-alerts.tf`:

```hcl
# NSG Monitoring Alerts

# High volume of blocked traffic
resource "azurerm_monitor_scheduled_query_rules_alert" "nsg_blocked_traffic" {
  name                = "pulse-nsg-blocked-traffic"
  location            = var.location
  resource_group_name = var.resource_group_name

  action {
    action_group = [var.alert_action_group_id]
  }

  data_source_id = var.log_analytics_workspace_id
  description    = "High volume of blocked network traffic detected"
  enabled        = true

  query = <<-QUERY
    AzureNetworkAnalytics_CL
    | where TimeGenerated > ago(15m)
    | where FlowStatus_s == "D"
    | summarize blocked_count = count()
  QUERY

  severity    = 2
  frequency   = 5
  time_window = 15

  trigger {
    operator  = "GreaterThan"
    threshold = 1000
  }
}

# Potential port scanning
resource "azurerm_monitor_scheduled_query_rules_alert" "nsg_port_scan" {
  name                = "pulse-nsg-port-scan"
  location            = var.location
  resource_group_name = var.resource_group_name

  action {
    action_group = [var.alert_action_group_id]
  }

  data_source_id = var.log_analytics_workspace_id
  description    = "Potential port scanning activity detected"
  enabled        = true

  query = <<-QUERY
    AzureNetworkAnalytics_CL
    | where TimeGenerated > ago(15m)
    | where FlowStatus_s == "D"
    | summarize unique_ports = dcount(DestPort_d) by SrcIP_s
    | where unique_ports > 20
  QUERY

  severity    = 1
  frequency   = 5
  time_window = 15

  trigger {
    operator  = "GreaterThan"
    threshold = 0
  }
}

# Unusual outbound traffic
resource "azurerm_monitor_scheduled_query_rules_alert" "nsg_unusual_outbound" {
  name                = "pulse-nsg-unusual-outbound"
  location            = var.location
  resource_group_name = var.resource_group_name

  action {
    action_group = [var.alert_action_group_id]
  }

  data_source_id = var.log_analytics_workspace_id
  description    = "Unusual outbound traffic volume detected"
  enabled        = true

  query = <<-QUERY
    AzureNetworkAnalytics_CL
    | where TimeGenerated > ago(15m)
    | where FlowDirection_s == "O"
    | summarize total_bytes = sum(toint(OutboundBytes_d))
    | where total_bytes > 1073741824  // 1 GB
  QUERY

  severity    = 2
  frequency   = 15
  time_window = 30

  trigger {
    operator  = "GreaterThan"
    threshold = 0
  }
}
```

---

## Testing and Validation

### NSG Validation Script

Create `scripts/validate-nsg.sh`:

```bash
#!/bin/bash
# PULSE NSG Validation Script

set -e

RESOURCE_GROUP="${1:-rg-pulse-prod}"
echo "Validating NSGs in resource group: $RESOURCE_GROUP"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Get all NSGs
echo "=== NSG Inventory ==="
az network nsg list -g "$RESOURCE_GROUP" -o table

echo ""
echo "=== NSG Rule Analysis ==="

for nsg in $(az network nsg list -g "$RESOURCE_GROUP" --query "[].name" -o tsv); do
    echo ""
    echo "--- NSG: $nsg ---"

    # Check for DenyAll rules
    deny_inbound=$(az network nsg rule list -g "$RESOURCE_GROUP" --nsg-name "$nsg" \
        --query "[?access=='Deny' && direction=='Inbound' && priority>=4000]" -o tsv | wc -l)

    if [ "$deny_inbound" -gt 0 ]; then
        echo -e "${GREEN}✓ Has DenyAll inbound rule${NC}"
    else
        echo -e "${YELLOW}⚠ Missing DenyAll inbound rule${NC}"
    fi

    # Check for overly permissive rules
    any_any_rules=$(az network nsg rule list -g "$RESOURCE_GROUP" --nsg-name "$nsg" \
        --query "[?sourceAddressPrefix=='*' && destinationAddressPrefix=='*' && access=='Allow']" -o tsv | wc -l)

    if [ "$any_any_rules" -gt 0 ]; then
        echo -e "${RED}✗ Has overly permissive rules (source=*, dest=*)${NC}"
    else
        echo -e "${GREEN}✓ No overly permissive rules${NC}"
    fi

    # Check for internet-facing rules
    internet_rules=$(az network nsg rule list -g "$RESOURCE_GROUP" --nsg-name "$nsg" \
        --query "[?sourceAddressPrefix=='Internet' && access=='Allow']" -o tsv | wc -l)

    if [ "$internet_rules" -gt 0 ]; then
        echo -e "${YELLOW}⚠ Has rules allowing Internet traffic${NC}"
    else
        echo -e "${GREEN}✓ No direct Internet allow rules${NC}"
    fi

    # Show effective rules
    echo "  Rules:"
    az network nsg rule list -g "$RESOURCE_GROUP" --nsg-name "$nsg" \
        --query "[].{Name:name, Priority:priority, Access:access, Direction:direction, Source:sourceAddressPrefix, Dest:destinationAddressPrefix, Port:destinationPortRange}" \
        -o table
done

echo ""
echo "=== Subnet NSG Associations ==="
az network vnet list -g "$RESOURCE_GROUP" --query "[].{VNet:name, Subnets:subnets[].{Name:name, NSG:networkSecurityGroup.id}}" -o json | \
    jq -r '.[] | "\(.VNet):" , (.Subnets[] | "  \(.Name): \(.NSG // "NO NSG")")'

echo ""
echo "=== Flow Logs Status ==="
az network watcher flow-log list -l eastus -o table 2>/dev/null || echo "Flow logs not found or Network Watcher not enabled"

echo ""
echo "=== Validation Complete ==="
```

### Connectivity Test Script

Create `scripts/test-nsg-connectivity.sh`:

```bash
#!/bin/bash
# Test NSG connectivity between subnets

set -e

RESOURCE_GROUP="${1:-rg-pulse-prod}"
VNET="${2:-vnet-pulse-prod}"

echo "Testing NSG connectivity in $VNET"
echo ""

# Test endpoints
declare -A ENDPOINTS=(
    ["Web to Function"]="10.0.2.0:443"
    ["Web to OpenAI PE"]="10.0.3.10:443"
    ["Function to Postgres PE"]="10.0.3.20:5432"
    ["Function to Storage PE"]="10.0.3.30:443"
)

for test_name in "${!ENDPOINTS[@]}"; do
    endpoint="${ENDPOINTS[$test_name]}"
    ip=$(echo $endpoint | cut -d: -f1)
    port=$(echo $endpoint | cut -d: -f2)

    echo -n "Testing $test_name ($endpoint): "

    # Use az network watcher check-connectivity for real testing
    # This is a simplified example
    result=$(az network watcher test-ip-flow \
        --direction Inbound \
        --protocol TCP \
        --local "${ip}:${port}" \
        --remote "10.0.1.100:50000" \
        --resource-group "$RESOURCE_GROUP" \
        --vm "test-vm" \
        --query "access" -o tsv 2>/dev/null || echo "UNKNOWN")

    if [ "$result" == "Allow" ]; then
        echo -e "\033[0;32mALLOWED\033[0m"
    elif [ "$result" == "Deny" ]; then
        echo -e "\033[0;31mDENIED\033[0m"
    else
        echo -e "\033[1;33mUNKNOWN\033[0m"
    fi
done
```

---

## Migration Checklist

### Phase 1: Assessment

- [ ] Inventory existing NSGs and rules
- [ ] Document current subnet configurations
- [ ] Identify all required traffic flows
- [ ] Map application communication patterns

### Phase 2: Design

- [ ] Design subnet structure with address ranges
- [ ] Define NSG rules for each subnet
- [ ] Plan ASG groupings
- [ ] Document rule justifications

### Phase 3: Implementation

- [ ] Create NSG Terraform module
- [ ] Configure web subnet NSG
- [ ] Configure function subnet NSG
- [ ] Configure private endpoint subnet NSG
- [ ] Enable private endpoint network policies
- [ ] Create ASGs and ASG-based rules

### Phase 4: Flow Logs

- [ ] Create storage account for flow logs
- [ ] Enable NSG flow logs for all NSGs
- [ ] Configure Traffic Analytics
- [ ] Deploy Log Analytics queries

### Phase 5: Validation

- [ ] Run NSG validation script
- [ ] Test connectivity between subnets
- [ ] Verify Private Endpoint access
- [ ] Test from web app to function app
- [ ] Test function app to database

### Phase 6: Monitoring

- [ ] Deploy alert rules
- [ ] Configure notification channels
- [ ] Create monitoring dashboard
- [ ] Document incident response procedures

---

## Best Practices Summary

1. **Deny by Default**: Always include explicit deny rules
2. **Least Privilege**: Only allow necessary traffic
3. **Subnet-Level**: Apply NSGs to subnets, not NICs
4. **Document Rules**: Use descriptions for all rules
5. **Service Tags**: Use Azure service tags where possible
6. **ASGs**: Use Application Security Groups for logical grouping
7. **Flow Logs**: Enable for visibility and compliance
8. **Regular Review**: Audit NSG rules periodically

---

## Related Documents

- [securedbydesign.md](securedbydesign.md) - Overall security assessment
- [settofalse.md](settofalse.md) - Private Link configuration
- [wafconfig.md](wafconfig.md) - Web Application Firewall
- [ratelimiting.md](ratelimiting.md) - Rate limiting implementation
