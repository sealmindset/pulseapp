# PULSE Platform - Secrets Management Implementation Guide

> **Document Version:** 1.0
> **Created:** December 25, 2024
> **Classification:** RESTRICTED - Internal Use Only
> **Related Documents:** [securedbydesign.md](securedbydesign.md), [settofalse.md](settofalse.md)

---

## Executive Summary

This document provides a comprehensive guide for implementing secure secrets management in the PULSE platform using **Azure Key Vault** and **GitHub Secrets**. It covers the migration from the current state (plaintext secrets in Terraform variables and environment variables) to a secure secrets management architecture.

**Current Risk Level:** CRITICAL - Credentials have been exposed in git history and must be rotated immediately.

---

## Table of Contents

- [1. Current State Assessment](#1-current-state-assessment)
- [2. Target Architecture](#2-target-architecture)
- [3. Azure Key Vault Implementation](#3-azure-key-vault-implementation)
- [4. GitHub Secrets Configuration](#4-github-secrets-configuration)
- [5. Application Code Changes](#5-application-code-changes)
- [6. Terraform Code Changes](#6-terraform-code-changes)
- [7. CI/CD Pipeline Updates](#7-cicd-pipeline-updates)
- [8. Secret Rotation Procedures](#8-secret-rotation-procedures)
- [9. Migration Checklist](#9-migration-checklist)
- [10. Troubleshooting](#10-troubleshooting)

---

## 1. Current State Assessment

### 1.1 Secrets Inventory

| Secret | Current Location | Risk Level | Action Required |
|--------|------------------|------------|-----------------|
| Azure AD Client ID | `prod.tfvars` | MEDIUM | Move to Key Vault |
| Azure AD Client Secret | `prod.tfvars` | **CRITICAL** | Rotate + Key Vault |
| Azure AD Tenant ID | `prod.tfvars` | MEDIUM | Move to Key Vault |
| NextAuth Secret | `prod.tfvars` | **CRITICAL** | Rotate + Key Vault |
| PostgreSQL Password | `prod.tfvars` | **CRITICAL** | Rotate + Key Vault |
| OpenAI API Key | App Settings | HIGH | Move to Key Vault |
| Storage Connection String | App Settings | HIGH | Use Managed Identity |
| Speech Services Key | App Settings | HIGH | Move to Key Vault |
| Subscription ID | `prod.tfvars` | LOW | Keep in tfvars |

### 1.2 Current Security Gaps

```
CRITICAL ISSUES:
├── prod.tfvars committed to git with real credentials
├── No Azure Key Vault configured
├── Plaintext secrets in Terraform state
├── Database password embedded in connection string
├── Hardcoded NEXTAUTH_SECRET fallback in code
└── No secret rotation schedule
```

### 1.3 Files Containing Secrets

| File | Secrets Present | Action |
|------|-----------------|--------|
| `prod.tfvars` | Azure AD, NextAuth, DB password | Remove from git, use Key Vault |
| `ui/lib/auth-config.ts` | Hardcoded fallback secret | Remove fallback |
| `orchestrator/shared_code/analytics_db.py` | Password in DSN | Use managed identity |
| `orchestrator/shared_code/blob.py` | Connection string | Use managed identity |
| `.tfstate` (local) | All secrets in plaintext | Use remote backend |

---

## 2. Target Architecture

### 2.1 Secrets Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           SECRETS MANAGEMENT ARCHITECTURE                    │
└─────────────────────────────────────────────────────────────────────────────┘

  ┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
  │  GitHub Secrets  │     │  Azure Key Vault │     │ Managed Identity │
  │  ─────────────── │     │  ─────────────── │     │  ─────────────── │
  │  • AZURE_CREDS   │     │  • App Secrets   │     │  • Storage Access│
  │  • TF_VAR_*      │     │  • API Keys      │     │  • DB Access     │
  │  • Deploy Keys   │     │  • Certificates  │     │  • OpenAI Access │
  └────────┬─────────┘     └────────┬─────────┘     └────────┬─────────┘
           │                        │                        │
           ▼                        ▼                        ▼
  ┌─────────────────────────────────────────────────────────────────────────┐
  │                           CI/CD PIPELINE                                 │
  │  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                 │
  │  │   GitHub    │───▶│  Terraform  │───▶│   Azure     │                 │
  │  │   Actions   │    │   Apply     │    │  Resources  │                 │
  │  └─────────────┘    └─────────────┘    └─────────────┘                 │
  └─────────────────────────────────────────────────────────────────────────┘
           │                        │                        │
           ▼                        ▼                        ▼
  ┌─────────────────────────────────────────────────────────────────────────┐
  │                           RUNTIME ACCESS                                 │
  │  ┌─────────────────────────────────────────────────────────────────┐   │
  │  │  Web App / Function App                                          │   │
  │  │  ───────────────────────                                         │   │
  │  │  • Key Vault References in App Settings                          │   │
  │  │    @Microsoft.KeyVault(SecretUri=https://kv-pulse.../secrets/x) │   │
  │  │  • Managed Identity for Azure Resources (no keys needed)         │   │
  │  │  • DefaultAzureCredential for SDK authentication                 │   │
  │  └─────────────────────────────────────────────────────────────────┘   │
  └─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Secret Categories

| Category | Storage Location | Access Method |
|----------|------------------|---------------|
| **CI/CD Credentials** | GitHub Secrets | `${{ secrets.* }}` |
| **Application Secrets** | Azure Key Vault | Key Vault References |
| **Azure Resource Access** | Managed Identity | DefaultAzureCredential |
| **Terraform State** | Azure Storage (encrypted) | SAS Token / Managed Identity |

---

## 3. Azure Key Vault Implementation

### 3.1 Create Key Vault via Terraform

Add a new Key Vault module to your Terraform configuration:

**File: `modules/keyvault/main.tf`**

```hcl
# Azure Key Vault for secrets management
resource "azurerm_key_vault" "main" {
  name                        = "kv-PULSE-${var.environment}"
  location                    = var.location
  resource_group_name         = var.resource_group_name
  tenant_id                   = var.tenant_id
  sku_name                    = "standard"
  soft_delete_retention_days  = 90
  purge_protection_enabled    = true

  # Enable RBAC authorization (recommended over access policies)
  enable_rbac_authorization   = true

  # Network rules - restrict to VNet
  network_acls {
    default_action             = "Deny"
    bypass                     = "AzureServices"
    virtual_network_subnet_ids = [var.app_subnet_id]
    ip_rules                   = var.allowed_ip_ranges
  }

  tags = var.tags
}

# Private Endpoint for Key Vault
resource "azurerm_private_endpoint" "keyvault" {
  name                = "pe-PULSE-keyvault-${var.environment}"
  location            = var.location
  resource_group_name = var.resource_group_name
  subnet_id           = var.private_endpoint_subnet_id

  private_service_connection {
    name                           = "psc-keyvault"
    private_connection_resource_id = azurerm_key_vault.main.id
    is_manual_connection           = false
    subresource_names              = ["vault"]
  }

  private_dns_zone_group {
    name                 = "keyvault-dns-zone-group"
    private_dns_zone_ids = [var.keyvault_private_dns_zone_id]
  }

  tags = var.tags
}

# Private DNS Zone for Key Vault
resource "azurerm_private_dns_zone" "keyvault" {
  name                = "privatelink.vaultcore.azure.net"
  resource_group_name = var.resource_group_name
  tags                = var.tags
}

resource "azurerm_private_dns_zone_virtual_network_link" "keyvault" {
  name                  = "keyvault-dns-link"
  resource_group_name   = var.resource_group_name
  private_dns_zone_name = azurerm_private_dns_zone.keyvault.name
  virtual_network_id    = var.vnet_id
  registration_enabled  = false
  tags                  = var.tags
}

# Grant Web App access to Key Vault
resource "azurerm_role_assignment" "webapp_keyvault" {
  scope                = azurerm_key_vault.main.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = var.webapp_principal_id
}

# Grant Function App access to Key Vault
resource "azurerm_role_assignment" "funcapp_keyvault" {
  scope                = azurerm_key_vault.main.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = var.funcapp_principal_id
}
```

**File: `modules/keyvault/variables.tf`**

```hcl
variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "location" {
  description = "Azure region"
  type        = string
}

variable "resource_group_name" {
  description = "Resource group name"
  type        = string
}

variable "tenant_id" {
  description = "Azure AD tenant ID"
  type        = string
}

variable "app_subnet_id" {
  description = "App subnet ID for network rules"
  type        = string
}

variable "private_endpoint_subnet_id" {
  description = "Private endpoint subnet ID"
  type        = string
}

variable "vnet_id" {
  description = "Virtual network ID"
  type        = string
}

variable "webapp_principal_id" {
  description = "Web App managed identity principal ID"
  type        = string
}

variable "funcapp_principal_id" {
  description = "Function App managed identity principal ID"
  type        = string
}

variable "allowed_ip_ranges" {
  description = "IP ranges allowed to access Key Vault"
  type        = list(string)
  default     = []
}

variable "tags" {
  description = "Resource tags"
  type        = map(string)
  default     = {}
}
```

**File: `modules/keyvault/outputs.tf`**

```hcl
output "key_vault_id" {
  description = "Key Vault resource ID"
  value       = azurerm_key_vault.main.id
}

output "key_vault_uri" {
  description = "Key Vault URI"
  value       = azurerm_key_vault.main.vault_uri
}

output "key_vault_name" {
  description = "Key Vault name"
  value       = azurerm_key_vault.main.name
}
```

### 3.2 Store Secrets in Key Vault

**File: `modules/keyvault/secrets.tf`**

```hcl
# Azure AD Client Secret
resource "azurerm_key_vault_secret" "azure_ad_client_secret" {
  name         = "azure-ad-client-secret"
  value        = var.azure_ad_client_secret
  key_vault_id = azurerm_key_vault.main.id

  content_type = "text/plain"

  tags = {
    purpose     = "Azure AD OIDC authentication"
    rotation    = "90-days"
    environment = var.environment
  }

  # Depend on RBAC assignments
  depends_on = [
    azurerm_role_assignment.terraform_keyvault_admin
  ]
}

# NextAuth Secret
resource "azurerm_key_vault_secret" "nextauth_secret" {
  name         = "nextauth-secret"
  value        = var.nextauth_secret
  key_vault_id = azurerm_key_vault.main.id

  content_type = "text/plain"

  tags = {
    purpose     = "NextAuth.js session encryption"
    rotation    = "90-days"
    environment = var.environment
  }

  depends_on = [
    azurerm_role_assignment.terraform_keyvault_admin
  ]
}

# PostgreSQL Admin Password
resource "azurerm_key_vault_secret" "pg_admin_password" {
  name         = "pg-admin-password"
  value        = var.analytics_pg_admin_password
  key_vault_id = azurerm_key_vault.main.id

  content_type = "text/plain"

  tags = {
    purpose     = "PostgreSQL admin access"
    rotation    = "90-days"
    environment = var.environment
  }

  depends_on = [
    azurerm_role_assignment.terraform_keyvault_admin
  ]
}

# OpenAI API Key
resource "azurerm_key_vault_secret" "openai_api_key" {
  name         = "openai-api-key"
  value        = var.openai_api_key
  key_vault_id = azurerm_key_vault.main.id

  content_type = "text/plain"

  tags = {
    purpose     = "Azure OpenAI service access"
    rotation    = "180-days"
    environment = var.environment
  }

  depends_on = [
    azurerm_role_assignment.terraform_keyvault_admin
  ]
}

# Speech Services Key
resource "azurerm_key_vault_secret" "speech_key" {
  name         = "speech-key"
  value        = var.speech_key
  key_vault_id = azurerm_key_vault.main.id

  content_type = "text/plain"

  tags = {
    purpose     = "Azure Speech Services"
    rotation    = "180-days"
    environment = var.environment
  }

  depends_on = [
    azurerm_role_assignment.terraform_keyvault_admin
  ]
}

# Storage Account Key (if not using managed identity)
resource "azurerm_key_vault_secret" "storage_key" {
  name         = "storage-primary-key"
  value        = var.storage_account_primary_access_key
  key_vault_id = azurerm_key_vault.main.id

  content_type = "text/plain"

  tags = {
    purpose     = "Azure Storage access (prefer managed identity)"
    rotation    = "90-days"
    environment = var.environment
  }

  depends_on = [
    azurerm_role_assignment.terraform_keyvault_admin
  ]
}

# Terraform service principal access to Key Vault (for secret creation)
resource "azurerm_role_assignment" "terraform_keyvault_admin" {
  scope                = azurerm_key_vault.main.id
  role_definition_name = "Key Vault Administrator"
  principal_id         = var.terraform_principal_id
}
```

### 3.3 Key Vault References in App Settings

Update your App Service configuration to use Key Vault references instead of plaintext values:

**File: `modules/app/main.tf`** (Updated Web App section)

```hcl
resource "azurerm_linux_web_app" "ui" {
  name                = "app-PULSE-${var.project_name}-ui-${var.environment}"
  location            = var.location
  resource_group_name = var.resource_group_name
  service_plan_id     = azurerm_service_plan.main.id
  https_only          = true

  # Enable system-assigned managed identity
  identity {
    type = "SystemAssigned"
  }

  site_config {
    always_on                = true
    ftps_state               = "Disabled"
    minimum_tls_version      = "1.2"
    vnet_route_all_enabled   = true

    application_stack {
      node_version = "20-lts"
    }
  }

  app_settings = {
    # Non-sensitive configuration
    "WEBSITE_NODE_DEFAULT_VERSION" = "~20"
    "SCM_DO_BUILD_DURING_DEPLOYMENT" = "true"
    "NEXT_PUBLIC_ENV_NAME"           = var.environment

    # Key Vault References for secrets
    # Format: @Microsoft.KeyVault(SecretUri=https://{vault-name}.vault.azure.net/secrets/{secret-name}/)
    "AZURE_AD_CLIENT_ID"     = var.azure_ad_client_id  # Not sensitive, can be plaintext
    "AZURE_AD_TENANT_ID"     = var.azure_ad_tenant_id  # Not sensitive, can be plaintext
    "AZURE_AD_CLIENT_SECRET" = "@Microsoft.KeyVault(SecretUri=${var.keyvault_uri}secrets/azure-ad-client-secret/)"
    "NEXTAUTH_SECRET"        = "@Microsoft.KeyVault(SecretUri=${var.keyvault_uri}secrets/nextauth-secret/)"
    "NEXTAUTH_URL"           = "https://${var.webapp_hostname}"
    "AUTH_MODE"              = var.auth_mode

    # Function App integration
    "FUNCTION_APP_BASE_URL"  = "https://${var.function_app_hostname}"

    # Application Insights (not sensitive)
    "APPLICATIONINSIGHTS_CONNECTION_STRING" = var.appinsights_connection_string
  }

  # Virtual network integration
  virtual_network_subnet_id = var.app_subnet_id

  tags = var.tags
}
```

**File: `modules/app/main.tf`** (Updated Function App section)

```hcl
resource "azurerm_linux_function_app" "orchestrator" {
  name                       = "func-PULSE-${var.project_name}-orchestrator-${var.environment}"
  location                   = var.location
  resource_group_name        = var.resource_group_name
  service_plan_id            = azurerm_service_plan.main.id
  storage_account_name       = var.storage_account_name
  storage_account_access_key = null  # Use managed identity instead

  # Enable system-assigned managed identity
  identity {
    type = "SystemAssigned"
  }

  site_config {
    always_on                = true
    ftps_state               = "Disabled"
    minimum_tls_version      = "1.2"
    vnet_route_all_enabled   = true

    application_stack {
      python_version = "3.11"
    }
  }

  app_settings = {
    # Runtime configuration
    "FUNCTIONS_WORKER_RUNTIME"       = "python"
    "PYTHON_ENABLE_WORKER_EXTENSIONS" = "1"

    # Storage - Use managed identity
    "AzureWebJobsStorage__accountName" = var.storage_account_name
    # When using managed identity, use this format instead of connection string

    # OpenAI Configuration
    "OPENAI_ENDPOINT"                          = var.openai_endpoint
    "OPENAI_API_VERSION"                       = var.openai_api_version
    "OPENAI_DEPLOYMENT_PERSONA_CORE_CHAT"      = var.openai_deployment_chat
    "OPENAI_DEPLOYMENT_PERSONA_HIGH_REASONING" = var.openai_deployment_reasoning
    "OPENAI_DEPLOYMENT_PULSE_AUDIO_REALTIME"   = var.openai_deployment_audio
    "OPENAI_DEPLOYMENT_WHISPER"                = var.openai_deployment_whisper

    # Key Vault References for secrets
    "AZURE_OPENAI_API_KEY"       = "@Microsoft.KeyVault(SecretUri=${var.keyvault_uri}secrets/openai-api-key/)"
    "AZURE_SPEECH_KEY"           = "@Microsoft.KeyVault(SecretUri=${var.keyvault_uri}secrets/speech-key/)"
    "PULSE_ANALYTICS_DB_PASSWORD" = "@Microsoft.KeyVault(SecretUri=${var.keyvault_uri}secrets/pg-admin-password/)"

    # Database configuration (non-sensitive)
    "PULSE_ANALYTICS_DB_HOST" = var.pg_fqdn
    "PULSE_ANALYTICS_DB_NAME" = var.pg_database_name
    "PULSE_ANALYTICS_DB_USER" = var.pg_admin_username
    "PULSE_ANALYTICS_DB_PORT" = "5432"

    # Speech configuration (non-sensitive)
    "AZURE_SPEECH_REGION" = var.location

    # Application Insights
    "APPLICATIONINSIGHTS_CONNECTION_STRING" = var.appinsights_connection_string
  }

  # Virtual network integration
  virtual_network_subnet_id = var.app_subnet_id

  tags = var.tags
}
```

---

## 4. GitHub Secrets Configuration

### 4.1 Required GitHub Secrets

Configure these secrets in your GitHub repository settings (`Settings > Secrets and variables > Actions`):

| Secret Name | Description | How to Obtain |
|-------------|-------------|---------------|
| `AZURE_CREDENTIALS` | Azure service principal credentials | `az ad sp create-for-rbac` |
| `AZURE_SUBSCRIPTION_ID` | Azure subscription ID | Azure Portal |
| `AZURE_TENANT_ID` | Azure AD tenant ID | Azure Portal |
| `TF_VAR_azure_ad_client_secret` | Azure AD app client secret | Entra ID > App Registration |
| `TF_VAR_nextauth_secret` | NextAuth.js encryption key | `openssl rand -base64 32` |
| `TF_VAR_analytics_pg_admin_password` | PostgreSQL admin password | Generate secure password |
| `ARM_CLIENT_ID` | Terraform service principal client ID | `az ad sp create-for-rbac` output |
| `ARM_CLIENT_SECRET` | Terraform service principal secret | `az ad sp create-for-rbac` output |

### 4.2 Create Azure Service Principal for GitHub Actions

```bash
# Create service principal with Contributor role
az ad sp create-for-rbac \
  --name "sp-PULSE-github-actions" \
  --role "Contributor" \
  --scopes "/subscriptions/{subscription-id}/resourceGroups/rg-PULSE-training-prod" \
  --sdk-auth

# Output format for AZURE_CREDENTIALS secret:
{
  "clientId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "clientSecret": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "subscriptionId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "tenantId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "activeDirectoryEndpointUrl": "https://login.microsoftonline.com",
  "resourceManagerEndpointUrl": "https://management.azure.com/",
  "activeDirectoryGraphResourceId": "https://graph.windows.net/",
  "sqlManagementEndpointUrl": "https://management.core.windows.net:8443/",
  "galleryEndpointUrl": "https://gallery.azure.com/",
  "managementEndpointUrl": "https://management.core.windows.net/"
}
```

### 4.3 Generate Secure Secrets

```bash
# Generate NextAuth secret
openssl rand -base64 32
# Output: lfyQ4E4j+CoNjxEQFkV/H95nTvnU08J0q5/ISyzpQ60=

# Generate PostgreSQL password (strong, no special chars that break DSN)
openssl rand -base64 24 | tr -d '/+=' | head -c 32
# Output: xK9mN2pL5qR8sT1uV4wY7zA0bC3dE6fG

# Generate random API key replacement
openssl rand -hex 32
# Output: a1b2c3d4e5f6...
```

---

## 5. Application Code Changes

### 5.1 Next.js Authentication Configuration

**File: `ui/lib/auth-config.ts`** (Updated)

```typescript
import { getServerSession } from "next-auth";
import type { NextAuthOptions } from "next-auth";
import AzureADProvider from "next-auth/providers/azure-ad";

// SECURITY: Fail fast if required secrets are missing
// Do NOT use fallback values in production
function getRequiredEnvVar(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(
      `Missing required environment variable: ${name}. ` +
      `Ensure Key Vault references are configured correctly.`
    );
  }
  return value;
}

// Optional env var with explicit undefined (no insecure fallbacks)
function getOptionalEnvVar(name: string): string | undefined {
  return process.env[name] || undefined;
}

export const authOptions: NextAuthOptions = {
  providers: [
    AzureADProvider({
      clientId: getRequiredEnvVar("AZURE_AD_CLIENT_ID"),
      clientSecret: getRequiredEnvVar("AZURE_AD_CLIENT_SECRET"),
      tenantId: getRequiredEnvVar("AZURE_AD_TENANT_ID"),
      authorization: {
        params: {
          scope: "openid profile email User.Read",
        },
      },
    }),
  ],

  secret: getRequiredEnvVar("NEXTAUTH_SECRET"),

  session: {
    strategy: "jwt",
    maxAge: 8 * 60 * 60, // 8 hours
  },

  callbacks: {
    async jwt({ token, account, profile }) {
      if (account && profile) {
        token.accessToken = account.access_token;
        token.email = profile.email;
      }
      return token;
    },

    async session({ session, token }) {
      if (token) {
        session.accessToken = token.accessToken as string;
        session.user.email = token.email as string;
      }
      return session;
    },

    async signIn({ user, account, profile }) {
      // Validate user email domain if required
      const email = user.email || profile?.email;
      if (!email) {
        console.error("Sign-in rejected: No email provided");
        return false;
      }

      // Log successful sign-in (without sensitive data)
      console.log(`User signed in: ${email.split('@')[1]} domain`);
      return true;
    },
  },

  pages: {
    signIn: "/auth/signin",
    error: "/auth/error",
  },

  debug: process.env.NODE_ENV === "development",
};

export async function getServerAuthSession() {
  return await getServerSession(authOptions);
}
```

### 5.2 Python Function App - Azure Identity Integration

**File: `orchestrator/shared_code/azure_identity_helper.py`** (New file)

```python
"""
Azure Identity Helper - Centralized credential management using DefaultAzureCredential.

This module provides a unified way to authenticate to Azure services using
managed identity (in Azure) or developer credentials (locally).
"""

import os
import logging
from functools import lru_cache
from typing import Optional

from azure.identity import DefaultAzureCredential, ManagedIdentityCredential
from azure.keyvault.secrets import SecretClient

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_azure_credential() -> DefaultAzureCredential:
    """
    Get Azure credential using DefaultAzureCredential.

    This automatically handles:
    - Managed Identity (when running in Azure)
    - Azure CLI credentials (local development)
    - Environment variables (CI/CD)
    - Visual Studio Code credentials (local development)

    Returns:
        DefaultAzureCredential instance (cached)
    """
    return DefaultAzureCredential(
        exclude_interactive_browser_credential=True,
        exclude_shared_token_cache_credential=True,
    )


@lru_cache(maxsize=1)
def get_keyvault_client() -> Optional[SecretClient]:
    """
    Get Key Vault SecretClient for fetching secrets.

    Returns:
        SecretClient instance or None if Key Vault URI not configured
    """
    keyvault_uri = os.environ.get("AZURE_KEYVAULT_URI")

    if not keyvault_uri:
        logger.warning("AZURE_KEYVAULT_URI not set - Key Vault integration disabled")
        return None

    credential = get_azure_credential()
    return SecretClient(vault_url=keyvault_uri, credential=credential)


def get_secret(secret_name: str, default: Optional[str] = None) -> Optional[str]:
    """
    Fetch a secret from Azure Key Vault.

    Falls back to environment variable if Key Vault is not configured
    or secret is not found.

    Args:
        secret_name: Name of the secret in Key Vault (e.g., "openai-api-key")
        default: Default value if secret not found

    Returns:
        Secret value or default
    """
    # First check environment variable (for local dev or Key Vault reference)
    env_name = secret_name.upper().replace("-", "_")
    env_value = os.environ.get(env_name)

    if env_value:
        # Check if it's a Key Vault reference (starts with @Microsoft.KeyVault)
        if env_value.startswith("@Microsoft.KeyVault"):
            # Azure App Service resolves these automatically
            # If we see the raw reference, we're in local dev
            logger.debug(f"Key Vault reference detected for {secret_name}")
        else:
            return env_value

    # Try Key Vault directly
    client = get_keyvault_client()
    if client:
        try:
            secret = client.get_secret(secret_name)
            return secret.value
        except Exception as e:
            logger.warning(f"Failed to fetch secret '{secret_name}' from Key Vault: {e}")

    return default


def get_required_secret(secret_name: str) -> str:
    """
    Fetch a required secret - raises exception if not found.

    Args:
        secret_name: Name of the secret

    Returns:
        Secret value

    Raises:
        ValueError: If secret is not found
    """
    value = get_secret(secret_name)
    if not value:
        raise ValueError(
            f"Required secret '{secret_name}' not found. "
            f"Check Key Vault configuration or {secret_name.upper().replace('-', '_')} environment variable."
        )
    return value
```

### 5.3 Python Function App - OpenAI Client Update

**File: `orchestrator/shared_code/openai_client.py`** (Updated)

```python
"""
Azure OpenAI Client with secure credential handling.
"""

import os
import logging
from functools import lru_cache
from typing import Optional

from openai import AzureOpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

from .azure_identity_helper import get_azure_credential, get_secret

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_openai_client() -> AzureOpenAI:
    """
    Create Azure OpenAI client with secure authentication.

    Supports two authentication methods:
    1. Managed Identity (preferred for production)
    2. API Key (fallback, fetched from Key Vault)

    Returns:
        Configured AzureOpenAI client
    """
    endpoint = os.environ.get("OPENAI_ENDPOINT")
    api_version = os.environ.get("OPENAI_API_VERSION", "2024-02-15-preview")

    if not endpoint:
        raise ValueError("OPENAI_ENDPOINT environment variable is required")

    # Try managed identity first (preferred)
    use_managed_identity = os.environ.get("OPENAI_USE_MANAGED_IDENTITY", "false").lower() == "true"

    if use_managed_identity:
        logger.info("Using managed identity for Azure OpenAI authentication")
        credential = get_azure_credential()
        token_provider = get_bearer_token_provider(
            credential,
            "https://cognitiveservices.azure.com/.default"
        )

        return AzureOpenAI(
            azure_endpoint=endpoint,
            api_version=api_version,
            azure_ad_token_provider=token_provider,
        )
    else:
        # Fall back to API key (from Key Vault or environment)
        api_key = get_secret("openai-api-key") or os.environ.get("AZURE_OPENAI_API_KEY")

        if not api_key:
            raise ValueError(
                "Azure OpenAI API key not found. "
                "Set OPENAI_USE_MANAGED_IDENTITY=true or configure openai-api-key in Key Vault."
            )

        logger.info("Using API key for Azure OpenAI authentication")
        return AzureOpenAI(
            azure_endpoint=endpoint,
            api_version=api_version,
            api_key=api_key,
        )


def get_deployment_name(deployment_type: str) -> str:
    """
    Get deployment name for a specific model type.

    Args:
        deployment_type: One of 'chat', 'reasoning', 'audio', 'whisper', 'visual'

    Returns:
        Deployment name from environment
    """
    deployment_map = {
        "chat": "OPENAI_DEPLOYMENT_PERSONA_CORE_CHAT",
        "reasoning": "OPENAI_DEPLOYMENT_PERSONA_HIGH_REASONING",
        "audio": "OPENAI_DEPLOYMENT_PULSE_AUDIO_REALTIME",
        "whisper": "OPENAI_DEPLOYMENT_WHISPER",
        "visual": "OPENAI_DEPLOYMENT_PERSONA_VISUAL_ASSET",
    }

    env_var = deployment_map.get(deployment_type)
    if not env_var:
        raise ValueError(f"Unknown deployment type: {deployment_type}")

    value = os.environ.get(env_var)
    if not value:
        raise ValueError(f"Deployment not configured: {env_var}")

    return value
```

### 5.4 Python Function App - Database Connection Update

**File: `orchestrator/shared_code/analytics_db.py`** (Updated)

```python
"""
PostgreSQL Analytics Database connection with secure credential handling.
"""

import os
import logging
from functools import lru_cache
from typing import Optional
from contextlib import contextmanager

import psycopg2
from psycopg2 import pool

from .azure_identity_helper import get_secret

logger = logging.getLogger(__name__)

# Connection pool (initialized lazily)
_connection_pool: Optional[pool.ThreadedConnectionPool] = None


def _get_connection_params() -> dict:
    """
    Get database connection parameters with secure password handling.

    Returns:
        Dictionary of connection parameters
    """
    host = os.environ.get("PULSE_ANALYTICS_DB_HOST")
    name = os.environ.get("PULSE_ANALYTICS_DB_NAME", "pulse_analytics")
    user = os.environ.get("PULSE_ANALYTICS_DB_USER")
    port = os.environ.get("PULSE_ANALYTICS_DB_PORT", "5432")

    if not host or not user:
        raise ValueError(
            "Database configuration incomplete. "
            "Required: PULSE_ANALYTICS_DB_HOST, PULSE_ANALYTICS_DB_USER"
        )

    # Get password from Key Vault or environment
    # SECURITY: Password is fetched at runtime, not stored in code
    password = get_secret("pg-admin-password") or os.environ.get("PULSE_ANALYTICS_DB_PASSWORD")

    if not password:
        raise ValueError(
            "Database password not found. "
            "Configure pg-admin-password in Key Vault or set PULSE_ANALYTICS_DB_PASSWORD."
        )

    return {
        "host": host,
        "port": int(port),
        "database": name,
        "user": user,
        "password": password,
        "sslmode": "require",  # Always require SSL
        "connect_timeout": 10,
    }


def get_connection_pool() -> pool.ThreadedConnectionPool:
    """
    Get or create the connection pool.

    Returns:
        ThreadedConnectionPool instance
    """
    global _connection_pool

    if _connection_pool is None:
        params = _get_connection_params()
        _connection_pool = pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            **params
        )
        logger.info(f"Database connection pool created for {params['host']}")

    return _connection_pool


@contextmanager
def get_db_connection():
    """
    Context manager for database connections.

    Automatically returns connection to pool when done.

    Usage:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
    """
    pool = get_connection_pool()
    conn = pool.getconn()

    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


def close_pool():
    """Close all connections in the pool."""
    global _connection_pool

    if _connection_pool:
        _connection_pool.closeall()
        _connection_pool = None
        logger.info("Database connection pool closed")
```

### 5.5 Python Function App - Blob Storage Update

**File: `orchestrator/shared_code/blob.py`** (Updated)

```python
"""
Azure Blob Storage client with managed identity support.
"""

import os
import logging
from functools import lru_cache
from typing import Optional

from azure.storage.blob import BlobServiceClient, ContainerClient
from azure.identity import DefaultAzureCredential

from .azure_identity_helper import get_azure_credential

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_blob_service_client() -> BlobServiceClient:
    """
    Create BlobServiceClient with secure authentication.

    Supports two authentication methods:
    1. Managed Identity (preferred for production)
    2. Connection String (fallback for local development)

    Returns:
        Configured BlobServiceClient
    """
    # Check for managed identity configuration
    storage_account_name = os.environ.get("STORAGE_ACCOUNT_NAME")
    use_managed_identity = os.environ.get("STORAGE_USE_MANAGED_IDENTITY", "true").lower() == "true"

    if storage_account_name and use_managed_identity:
        # Use managed identity (preferred)
        logger.info(f"Using managed identity for storage account: {storage_account_name}")
        account_url = f"https://{storage_account_name}.blob.core.windows.net"
        credential = get_azure_credential()
        return BlobServiceClient(account_url=account_url, credential=credential)

    # Fall back to connection string
    connection_string = _get_connection_string()

    if connection_string:
        logger.info("Using connection string for blob storage (consider using managed identity)")
        return BlobServiceClient.from_connection_string(connection_string)

    raise ValueError(
        "Blob storage not configured. "
        "Set STORAGE_ACCOUNT_NAME with managed identity, or provide a connection string."
    )


def _get_connection_string() -> Optional[str]:
    """
    Get storage connection string from environment.

    Checks multiple environment variable names for compatibility.
    """
    candidates = [
        "STORAGE_CONNECTION_STRING",
        "BLOB_CONN_STRING",
        "AZURE_STORAGE_CONNECTION_STRING",
        "AzureWebJobsStorage",
    ]

    for var_name in candidates:
        value = os.environ.get(var_name)
        if value and not value.startswith("@Microsoft.KeyVault"):
            return value

    return None


def get_container_client(container_name: str) -> ContainerClient:
    """
    Get a ContainerClient for the specified container.

    Args:
        container_name: Name of the blob container

    Returns:
        ContainerClient instance
    """
    service_client = get_blob_service_client()
    return service_client.get_container_client(container_name)


def upload_blob(container_name: str, blob_name: str, data: bytes, overwrite: bool = True) -> str:
    """
    Upload data to a blob.

    Args:
        container_name: Target container
        blob_name: Name/path of the blob
        data: Bytes to upload
        overwrite: Whether to overwrite existing blob

    Returns:
        Blob URL
    """
    container = get_container_client(container_name)
    blob_client = container.get_blob_client(blob_name)
    blob_client.upload_blob(data, overwrite=overwrite)

    return blob_client.url


def download_blob(container_name: str, blob_name: str) -> bytes:
    """
    Download a blob's contents.

    Args:
        container_name: Source container
        blob_name: Name/path of the blob

    Returns:
        Blob contents as bytes
    """
    container = get_container_client(container_name)
    blob_client = container.get_blob_client(blob_name)

    return blob_client.download_blob().readall()
```

---

## 6. Terraform Code Changes

### 6.1 Update Root main.tf

**File: `main.tf`** (Add Key Vault module)

```hcl
# Add Key Vault module
module "keyvault" {
  source = "./modules/keyvault"

  environment         = var.environment
  location            = var.location
  resource_group_name = azurerm_resource_group.main.name
  tenant_id           = var.azure_ad_tenant_id

  app_subnet_id              = module.network.app_subnet_id
  private_endpoint_subnet_id = module.network.private_endpoint_subnet_id
  vnet_id                    = module.network.vnet_id

  webapp_principal_id   = module.app.webapp_principal_id
  funcapp_principal_id  = module.app.funcapp_principal_id
  terraform_principal_id = data.azurerm_client_config.current.object_id

  # Secrets to store (passed from tfvars via GitHub Secrets in CI)
  azure_ad_client_secret          = var.azure_ad_client_secret
  nextauth_secret                 = var.nextauth_secret
  analytics_pg_admin_password     = var.analytics_pg_admin_password
  openai_api_key                  = var.openai_api_key
  speech_key                      = var.speech_key
  storage_account_primary_access_key = module.storage.primary_access_key

  allowed_ip_ranges = var.keyvault_allowed_ip_ranges
  tags              = local.common_tags
}

# Pass Key Vault URI to app module
module "app" {
  source = "./modules/app"

  # ... existing configuration ...

  # Add Key Vault URI
  keyvault_uri = module.keyvault.key_vault_uri
}
```

### 6.2 Configure Remote Backend

**File: `backend.tf`** (New file)

```hcl
# Remote backend configuration for secure state storage
terraform {
  backend "azurerm" {
    resource_group_name  = "rg-PULSE-tfstate"
    storage_account_name = "stpulsetfstate"
    container_name       = "tfstate"
    key                  = "pulse.terraform.tfstate"

    # Use Azure AD authentication instead of storage keys
    use_azuread_auth = true
  }
}
```

**Create backend storage (one-time setup):**

```bash
# Create resource group for Terraform state
az group create \
  --name rg-PULSE-tfstate \
  --location eastus

# Create storage account with secure settings
az storage account create \
  --name stpulsetfstate \
  --resource-group rg-PULSE-tfstate \
  --location eastus \
  --sku Standard_LRS \
  --kind StorageV2 \
  --https-only true \
  --min-tls-version TLS1_2 \
  --allow-blob-public-access false \
  --allow-shared-key-access false

# Create container
az storage container create \
  --name tfstate \
  --account-name stpulsetfstate \
  --auth-mode login

# Grant Terraform service principal access
az role assignment create \
  --role "Storage Blob Data Contributor" \
  --assignee <terraform-sp-object-id> \
  --scope /subscriptions/<subscription-id>/resourceGroups/rg-PULSE-tfstate/providers/Microsoft.Storage/storageAccounts/stpulsetfstate
```

### 6.3 Update prod.tfvars.example

**File: `prod.tfvars.example`** (Template without real secrets)

```hcl
# PULSE Platform - Production Environment Configuration
# ======================================================
#
# SECURITY NOTICE:
# - Do NOT commit real secrets to this file
# - Use GitHub Secrets for CI/CD pipelines
# - Use Azure Key Vault for runtime secrets
# - See docs/secretsmanage.md for implementation details
#
# For local development, copy to prod.tfvars and fill in values
# Ensure prod.tfvars is in .gitignore

# ----------------------------------------
# Environment & Subscription
# ----------------------------------------
environment     = "prod"
project_name    = "training"
subscription_id = "<your-subscription-id>"  # From Azure Portal

# ----------------------------------------
# Azure AD / Entra ID Configuration
# ----------------------------------------
# These values come from Entra ID > App Registrations
azure_ad_client_id  = "<app-client-id>"
azure_ad_tenant_id  = "<tenant-id>"

# SECRETS - Pass via TF_VAR_ environment variables or GitHub Secrets
# azure_ad_client_secret = "<from-github-secrets>"
# nextauth_secret        = "<from-github-secrets>"

# ----------------------------------------
# Authentication Mode
# ----------------------------------------
auth_mode = "sso"  # Options: "sso" (production), "bypass" (dev only)

# ----------------------------------------
# Database Configuration
# ----------------------------------------
analytics_pg_admin_username = "pulse_analytics_admin"
# analytics_pg_admin_password = "<from-github-secrets>"

# ----------------------------------------
# Network Security
# ----------------------------------------
openai_public_network_access_enabled = false  # MUST be false for production
webapp_public_network_access_enabled = false  # MUST be false for production
enable_webapp_private_endpoint       = true

# ----------------------------------------
# Key Vault Configuration
# ----------------------------------------
keyvault_allowed_ip_ranges = []  # Add admin IPs if needed for debugging

# ----------------------------------------
# Tags
# ----------------------------------------
tags = {
  Environment = "Production"
  Project     = "PULSE"
  ManagedBy   = "Terraform"
  CostCenter  = "Training"
}
```

---

## 7. CI/CD Pipeline Updates

### 7.1 Updated GitHub Actions Workflow

**File: `.github/workflows/ci-infra-ui.yml`** (Updated)

```yaml
name: Infrastructure & UI Deployment

on:
  push:
    branches: [main]
    paths:
      - 'modules/**'
      - 'ui/**'
      - '*.tf'
      - '.github/workflows/ci-infra-ui.yml'
  pull_request:
    branches: [main]
  workflow_dispatch:
    inputs:
      environment:
        description: 'Target environment'
        required: true
        default: 'staging'
        type: choice
        options:
          - staging
          - prod

env:
  TF_VERSION: '1.6.0'
  NODE_VERSION: '20'

jobs:
  # ============================================
  # Terraform Plan
  # ============================================
  terraform-plan:
    name: Terraform Plan
    runs-on: ubuntu-latest
    environment: ${{ github.event.inputs.environment || 'staging' }}

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Azure Login
        uses: azure/login@v1
        with:
          creds: ${{ secrets.AZURE_CREDENTIALS }}

      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: ${{ env.TF_VERSION }}

      - name: Terraform Init
        run: terraform init
        env:
          ARM_CLIENT_ID: ${{ secrets.ARM_CLIENT_ID }}
          ARM_CLIENT_SECRET: ${{ secrets.ARM_CLIENT_SECRET }}
          ARM_SUBSCRIPTION_ID: ${{ secrets.AZURE_SUBSCRIPTION_ID }}
          ARM_TENANT_ID: ${{ secrets.AZURE_TENANT_ID }}

      - name: Terraform Plan
        run: terraform plan -out=tfplan -input=false
        env:
          # Azure authentication
          ARM_CLIENT_ID: ${{ secrets.ARM_CLIENT_ID }}
          ARM_CLIENT_SECRET: ${{ secrets.ARM_CLIENT_SECRET }}
          ARM_SUBSCRIPTION_ID: ${{ secrets.AZURE_SUBSCRIPTION_ID }}
          ARM_TENANT_ID: ${{ secrets.AZURE_TENANT_ID }}

          # Terraform variables (from GitHub Secrets)
          TF_VAR_environment: ${{ github.event.inputs.environment || 'staging' }}
          TF_VAR_subscription_id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}
          TF_VAR_azure_ad_client_id: ${{ secrets.AZURE_AD_CLIENT_ID }}
          TF_VAR_azure_ad_client_secret: ${{ secrets.AZURE_AD_CLIENT_SECRET }}
          TF_VAR_azure_ad_tenant_id: ${{ secrets.AZURE_TENANT_ID }}
          TF_VAR_nextauth_secret: ${{ secrets.NEXTAUTH_SECRET }}
          TF_VAR_analytics_pg_admin_password: ${{ secrets.PG_ADMIN_PASSWORD }}
          TF_VAR_openai_api_key: ${{ secrets.OPENAI_API_KEY }}
          TF_VAR_speech_key: ${{ secrets.SPEECH_KEY }}

      # Note: Plan output may contain sensitive data
      # Consider encrypting or limiting access
      - name: Upload Plan
        uses: actions/upload-artifact@v4
        with:
          name: tfplan-${{ github.event.inputs.environment || 'staging' }}
          path: tfplan
          retention-days: 5

  # ============================================
  # Terraform Apply (Manual Approval Required)
  # ============================================
  terraform-apply:
    name: Terraform Apply
    runs-on: ubuntu-latest
    needs: terraform-plan
    if: github.ref == 'refs/heads/main' && github.event_name != 'pull_request'
    environment:
      name: ${{ github.event.inputs.environment || 'staging' }}
      # Requires manual approval for production

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Azure Login
        uses: azure/login@v1
        with:
          creds: ${{ secrets.AZURE_CREDENTIALS }}

      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: ${{ env.TF_VERSION }}

      - name: Download Plan
        uses: actions/download-artifact@v4
        with:
          name: tfplan-${{ github.event.inputs.environment || 'staging' }}

      - name: Terraform Init
        run: terraform init
        env:
          ARM_CLIENT_ID: ${{ secrets.ARM_CLIENT_ID }}
          ARM_CLIENT_SECRET: ${{ secrets.ARM_CLIENT_SECRET }}
          ARM_SUBSCRIPTION_ID: ${{ secrets.AZURE_SUBSCRIPTION_ID }}
          ARM_TENANT_ID: ${{ secrets.AZURE_TENANT_ID }}

      - name: Terraform Apply
        run: terraform apply -auto-approve tfplan
        env:
          ARM_CLIENT_ID: ${{ secrets.ARM_CLIENT_ID }}
          ARM_CLIENT_SECRET: ${{ secrets.ARM_CLIENT_SECRET }}
          ARM_SUBSCRIPTION_ID: ${{ secrets.AZURE_SUBSCRIPTION_ID }}
          ARM_TENANT_ID: ${{ secrets.AZURE_TENANT_ID }}

  # ============================================
  # UI Build & Deploy
  # ============================================
  deploy-ui:
    name: Build & Deploy UI
    runs-on: ubuntu-latest
    needs: terraform-apply
    if: github.ref == 'refs/heads/main'

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: ${{ env.NODE_VERSION }}
          cache: 'npm'
          cache-dependency-path: ui/package-lock.json

      - name: Install Dependencies
        run: npm ci
        working-directory: ui

      - name: Build
        run: npm run build
        working-directory: ui
        env:
          # Build-time environment variables only
          # No secrets should be needed at build time
          NEXT_PUBLIC_ENV_NAME: ${{ github.event.inputs.environment || 'staging' }}

      - name: Azure Login
        uses: azure/login@v1
        with:
          creds: ${{ secrets.AZURE_CREDENTIALS }}

      - name: Deploy to Azure Web App
        uses: azure/webapps-deploy@v2
        with:
          app-name: app-PULSE-training-ui-${{ github.event.inputs.environment || 'staging' }}
          package: ui/.next
```

---

## 8. Secret Rotation Procedures

### 8.1 Rotation Schedule

| Secret | Rotation Frequency | Automated | Owner |
|--------|-------------------|-----------|-------|
| Azure AD Client Secret | 90 days | No (manual) | Security |
| NextAuth Secret | 90 days | No (manual) | Security |
| PostgreSQL Password | 90 days | No (manual) | Infrastructure |
| OpenAI API Key | 180 days | No (manual) | Infrastructure |
| Speech Services Key | 180 days | No (manual) | Infrastructure |
| Storage Account Keys | 90 days | Yes (Azure) | Infrastructure |

### 8.2 Azure AD Client Secret Rotation

```bash
# Step 1: Create new client secret in Entra ID
# Azure Portal > Entra ID > App Registrations > PULSE App > Certificates & secrets

# Step 2: Update GitHub Secret
# GitHub > Repository > Settings > Secrets > AZURE_AD_CLIENT_SECRET

# Step 3: Update Key Vault
az keyvault secret set \
  --vault-name kv-PULSE-prod \
  --name azure-ad-client-secret \
  --value "<new-secret-value>"

# Step 4: Restart applications to pick up new secret
az webapp restart --name app-PULSE-training-ui-prod --resource-group rg-PULSE-training-prod
az functionapp restart --name func-PULSE-training-orchestrator-prod --resource-group rg-PULSE-training-prod

# Step 5: Verify authentication works
curl -I https://app-pulse-training-ui-prod.azurewebsites.net/api/health

# Step 6: Delete old secret from Entra ID (after verification)
```

### 8.3 NextAuth Secret Rotation

```bash
# Step 1: Generate new secret
NEW_SECRET=$(openssl rand -base64 32)
echo "New NextAuth secret generated (do not log in production)"

# Step 2: Update GitHub Secret
# GitHub > Repository > Settings > Secrets > NEXTAUTH_SECRET

# Step 3: Update Key Vault
az keyvault secret set \
  --vault-name kv-PULSE-prod \
  --name nextauth-secret \
  --value "$NEW_SECRET"

# Step 4: Restart Web App
az webapp restart --name app-PULSE-training-ui-prod --resource-group rg-PULSE-training-prod

# Note: Existing user sessions will be invalidated
# Users will need to re-authenticate
```

### 8.4 PostgreSQL Password Rotation

```bash
# Step 1: Generate new password
NEW_PASSWORD=$(openssl rand -base64 24 | tr -d '/+=' | head -c 32)

# Step 2: Update password in PostgreSQL
# Connect via Azure Portal or psql with current password
az postgres flexible-server parameter set \
  --resource-group rg-PULSE-training-prod \
  --server-name pg-PULSE-analytics-prod \
  --name password \
  --value "$NEW_PASSWORD"

# Step 3: Update GitHub Secret
# GitHub > Repository > Settings > Secrets > PG_ADMIN_PASSWORD

# Step 4: Update Key Vault
az keyvault secret set \
  --vault-name kv-PULSE-prod \
  --name pg-admin-password \
  --value "$NEW_PASSWORD"

# Step 5: Restart Function App
az functionapp restart --name func-PULSE-training-orchestrator-prod --resource-group rg-PULSE-training-prod

# Step 6: Verify database connectivity
az functionapp log tail --name func-PULSE-training-orchestrator-prod --resource-group rg-PULSE-training-prod
```

---

## 9. Migration Checklist

### Phase 1: Immediate Actions (Day 1)

- [ ] **Rotate all exposed credentials** (Azure AD secret, NextAuth secret)
- [ ] **Remove prod.tfvars from git history**
  ```bash
  # Use BFG Repo-Cleaner (faster than git-filter-branch)
  bfg --delete-files prod.tfvars
  git reflog expire --expire=now --all && git gc --prune=now --aggressive
  git push --force
  ```
- [ ] **Add prod.tfvars to .gitignore** (verify it's there)
- [ ] **Create GitHub Secrets** for all sensitive values
- [ ] **Update team about credential rotation** (sessions will be invalidated)

### Phase 2: Key Vault Setup (Days 2-3)

- [ ] **Deploy Key Vault module** via Terraform
- [ ] **Configure Private Endpoint** for Key Vault
- [ ] **Store secrets in Key Vault**
- [ ] **Grant managed identity access** to Web App and Function App
- [ ] **Test Key Vault reference resolution**

### Phase 3: Application Updates (Days 4-5)

- [ ] **Update Next.js auth configuration** (remove hardcoded fallback)
- [ ] **Update Python OpenAI client** (add managed identity support)
- [ ] **Update Python database client** (secure password handling)
- [ ] **Update Python blob client** (managed identity support)
- [ ] **Deploy and test changes**

### Phase 4: CI/CD Updates (Day 6)

- [ ] **Update GitHub Actions workflow** with new secret references
- [ ] **Configure remote Terraform backend**
- [ ] **Migrate existing state to remote backend**
- [ ] **Test full CI/CD pipeline**

### Phase 5: Validation (Day 7)

- [ ] **Verify all Key Vault references resolve**
- [ ] **Verify managed identity authentication works**
- [ ] **Verify no plaintext secrets in logs**
- [ ] **Verify secret rotation procedures**
- [ ] **Document any issues and resolutions**

---

## 10. Troubleshooting

### 10.1 Key Vault Reference Not Resolving

**Symptom:** App setting shows `@Microsoft.KeyVault(...)` instead of actual value

**Causes & Solutions:**

1. **Managed identity not enabled**
   ```bash
   # Verify identity is enabled
   az webapp identity show --name app-PULSE-training-ui-prod --resource-group rg-PULSE-training-prod
   ```

2. **Missing RBAC assignment**
   ```bash
   # Grant access
   az role assignment create \
     --role "Key Vault Secrets User" \
     --assignee <principal-id> \
     --scope /subscriptions/.../resourceGroups/.../providers/Microsoft.KeyVault/vaults/kv-PULSE-prod
   ```

3. **Network access blocked**
   - Ensure App Service VNet integration is enabled
   - Ensure Key Vault allows access from App Service subnet

4. **Secret name mismatch**
   - Verify secret name in Key Vault matches reference
   - Secret names are case-insensitive but should match

### 10.2 Managed Identity Authentication Failing

**Symptom:** `DefaultAzureCredential` fails to authenticate

**Solutions:**

1. **Verify identity is system-assigned**
   ```bash
   az webapp identity show --name <app-name> --resource-group <rg-name>
   ```

2. **Check RBAC assignments**
   ```bash
   az role assignment list --assignee <principal-id> --output table
   ```

3. **Verify correct scope**
   - Storage: `Storage Blob Data Contributor` on storage account
   - Key Vault: `Key Vault Secrets User` on vault
   - OpenAI: `Cognitive Services OpenAI User` on OpenAI account

### 10.3 GitHub Actions Secrets Not Working

**Symptom:** Terraform plan fails with missing variables

**Solutions:**

1. **Verify secret names match exactly**
   - GitHub secret: `AZURE_AD_CLIENT_SECRET`
   - Workflow reference: `${{ secrets.AZURE_AD_CLIENT_SECRET }}`
   - TF_VAR: `TF_VAR_azure_ad_client_secret`

2. **Check environment-specific secrets**
   - Secrets can be scoped to environments
   - Verify correct environment is selected

3. **Check for typos in workflow**
   ```yaml
   # Common mistake - wrong syntax
   TF_VAR_secret: ${{ secrets.SECRET }}  # Correct
   TF_VAR_secret: $secrets.SECRET        # Wrong
   ```

### 10.4 Database Connection Failing After Migration

**Symptom:** Function App can't connect to PostgreSQL

**Solutions:**

1. **Verify password in Key Vault**
   ```bash
   az keyvault secret show --vault-name kv-PULSE-prod --name pg-admin-password --query value -o tsv
   ```

2. **Check connection string format**
   - Don't include password in `PULSE_ANALYTICS_DB_*` env vars
   - Password should come from Key Vault reference

3. **Verify SSL configuration**
   - PostgreSQL Flexible Server requires SSL
   - Connection code must specify `sslmode=require`

---

## Appendix A: Security Best Practices Summary

| Practice | Implementation |
|----------|----------------|
| No secrets in code | Use Key Vault references |
| No secrets in git | Use .gitignore, GitHub Secrets |
| Least privilege | RBAC with minimal permissions |
| Secret rotation | 90-day schedule for critical secrets |
| Audit logging | Key Vault diagnostic logs |
| Network isolation | Private endpoints for Key Vault |
| Managed identity | Prefer over API keys where possible |
| Fail fast | No insecure fallback values |

---

## Appendix B: Quick Reference Commands

```bash
# List all secrets in Key Vault
az keyvault secret list --vault-name kv-PULSE-prod --output table

# Get a specific secret value
az keyvault secret show --vault-name kv-PULSE-prod --name <secret-name> --query value -o tsv

# Set/update a secret
az keyvault secret set --vault-name kv-PULSE-prod --name <secret-name> --value "<value>"

# List RBAC assignments for Key Vault
az role assignment list --scope /subscriptions/.../resourceGroups/.../providers/Microsoft.KeyVault/vaults/kv-PULSE-prod --output table

# Check Web App managed identity
az webapp identity show --name app-PULSE-training-ui-prod --resource-group rg-PULSE-training-prod

# View Key Vault references in app settings
az webapp config appsettings list --name app-PULSE-training-ui-prod --resource-group rg-PULSE-training-prod --query "[?contains(value, 'KeyVault')]"

# Restart to pick up new secrets
az webapp restart --name app-PULSE-training-ui-prod --resource-group rg-PULSE-training-prod
az functionapp restart --name func-PULSE-training-orchestrator-prod --resource-group rg-PULSE-training-prod
```

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2024-12-25 | Security Team | Initial comprehensive guide |

---

**Next Review Date:** After initial implementation
**Classification:** RESTRICTED - Internal Use Only
