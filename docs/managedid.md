# PULSE Platform - Managed Identity Implementation Guide

> **Document Version:** 1.0
> **Created:** December 25, 2024
> **Classification:** RESTRICTED - Internal Use Only
> **Related Documents:** [securedbydesign.md](securedbydesign.md), [secretsmanage.md](secretsmanage.md)

---

## Executive Summary

This document provides a comprehensive guide for implementing **Azure Managed Identities** and **SAS tokens** in the PULSE platform to eliminate the need for embedded credentials. Managed identities provide automatic credential management, rotation, and secure authentication to Azure services without storing secrets in code or configuration.

**Key Benefits:**
- No credentials to manage, rotate, or secure
- Automatic token refresh handled by Azure
- Reduced attack surface (no secrets to leak)
- Simplified compliance and auditing
- Works seamlessly with Azure RBAC

---

## Table of Contents

- [1. Understanding Managed Identities](#1-understanding-managed-identities)
- [2. Current State Assessment](#2-current-state-assessment)
- [3. Azure Storage with Managed Identity](#3-azure-storage-with-managed-identity)
- [4. Azure OpenAI with Managed Identity](#4-azure-openai-with-managed-identity)
- [5. Azure PostgreSQL with Managed Identity](#5-azure-postgresql-with-managed-identity)
- [6. Azure Key Vault with Managed Identity](#6-azure-key-vault-with-managed-identity)
- [7. SAS Token Implementation](#7-sas-token-implementation)
- [8. Terraform Infrastructure Changes](#8-terraform-infrastructure-changes)
- [9. Application Code Changes](#9-application-code-changes)
- [10. CI/CD Pipeline Updates](#10-cicd-pipeline-updates)
- [11. Migration Checklist](#11-migration-checklist)
- [12. Troubleshooting](#12-troubleshooting)

---

## 1. Understanding Managed Identities

### 1.1 Types of Managed Identities

| Type | Description | Use Case |
|------|-------------|----------|
| **System-Assigned** | Created with and tied to an Azure resource; deleted when resource is deleted | App Services, Function Apps, VMs |
| **User-Assigned** | Standalone Azure resource that can be shared across multiple resources | Multiple apps needing same permissions |

### 1.2 How Managed Identity Works

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    MANAGED IDENTITY AUTHENTICATION FLOW                      │
└─────────────────────────────────────────────────────────────────────────────┘

  ┌─────────────────┐          ┌─────────────────┐          ┌─────────────────┐
  │   Application   │          │   Azure AD      │          │  Target Service │
  │   (Web App)     │          │   (Entra ID)    │          │  (Storage/DB)   │
  └────────┬────────┘          └────────┬────────┘          └────────┬────────┘
           │                            │                            │
           │  1. Request token          │                            │
           │   (via IMDS endpoint)      │                            │
           │───────────────────────────▶│                            │
           │                            │                            │
           │  2. Return access token    │                            │
           │   (short-lived JWT)        │                            │
           │◀───────────────────────────│                            │
           │                            │                            │
           │  3. Call service with token                             │
           │────────────────────────────────────────────────────────▶│
           │                            │                            │
           │                            │  4. Validate token         │
           │                            │◀───────────────────────────│
           │                            │                            │
           │  5. Return data                                         │
           │◀────────────────────────────────────────────────────────│
           │                            │                            │

Key Points:
• Application never sees or handles credentials
• Tokens are automatically rotated (typically every 24 hours)
• Azure handles all cryptographic operations
• Works only within Azure (IMDS is Azure-internal)
```

### 1.3 DefaultAzureCredential Chain

The `DefaultAzureCredential` class tries multiple authentication methods in order:

```
┌────────────────────────────────────────────────────────────────────────────┐
│                    DefaultAzureCredential Authentication Chain              │
├────────────────────────────────────────────────────────────────────────────┤
│  1. Environment Variables      → For CI/CD pipelines                       │
│  2. Workload Identity         → For Kubernetes (AKS)                       │
│  3. Managed Identity          → For Azure resources (App Service, VM)      │
│  4. Azure CLI                 → For local development (`az login`)         │
│  5. Azure PowerShell          → For local development                      │
│  6. Azure Developer CLI       → For local development (`azd auth login`)   │
│  7. Interactive Browser       → Last resort (disabled by default)          │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Current State Assessment

### 2.1 Current Authentication Methods

| Service | Current Method | Risk Level | Target Method |
|---------|----------------|------------|---------------|
| Azure Storage | Connection String (access key) | **HIGH** | Managed Identity |
| Azure OpenAI | API Key | **HIGH** | Managed Identity |
| PostgreSQL | Password in connection string | **HIGH** | Managed Identity (AAD Auth) |
| Azure Key Vault | Not configured | N/A | Managed Identity |
| Azure Speech | API Key | MEDIUM | Managed Identity or Key Vault |

### 2.2 Current Configuration Issues

**Terraform (`prod.tfvars`):**
```hcl
# CURRENT - Using shared access keys
storage_account_shared_access_key_enabled = true   # INSECURE
storage_default_oauth_authentication = false        # Should be true
```

**Function App (`modules/app/main.tf`):**
```hcl
# CURRENT - Connection string with embedded key
"AzureWebJobsStorage" = var.storage_account_primary_connection_string  # INSECURE
```

**Python Code (`blob.py`):**
```python
# CURRENT - Using connection string
BlobServiceClient.from_connection_string(connection_string)  # INSECURE
```

---

## 3. Azure Storage with Managed Identity

### 3.1 Required RBAC Roles

| Role | Scope | Purpose |
|------|-------|---------|
| `Storage Blob Data Contributor` | Storage Account | Read/write blob data |
| `Storage Blob Data Reader` | Storage Account | Read-only blob access |
| `Storage Queue Data Contributor` | Storage Account | Function App triggers |
| `Storage Table Data Contributor` | Storage Account | Table storage access |

### 3.2 Terraform Configuration

**File: `modules/storage/main.tf`** (Updated)

```hcl
resource "azurerm_storage_account" "main" {
  name                            = "stpulse${var.environment}"
  resource_group_name             = var.resource_group_name
  location                        = var.location
  account_tier                    = "Standard"
  account_replication_type        = "LRS"

  # SECURITY: Disable shared key access, require Azure AD
  shared_access_key_enabled       = false
  default_to_oauth_authentication = true

  # SECURITY: Require HTTPS and TLS 1.2+
  https_traffic_only_enabled      = true
  min_tls_version                 = "TLS1_2"

  # SECURITY: Disable public blob access
  allow_nested_items_to_be_public = false
  public_network_access_enabled   = var.public_network_access_enabled

  # Enable blob versioning for audit trail
  blob_properties {
    versioning_enabled = true

    delete_retention_policy {
      days = 30
    }

    container_delete_retention_policy {
      days = 30
    }
  }

  tags = var.tags
}

# RBAC: Grant Web App access to blob storage
resource "azurerm_role_assignment" "webapp_storage_blob" {
  scope                = azurerm_storage_account.main.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = var.webapp_principal_id
}

# RBAC: Grant Function App access to blob storage
resource "azurerm_role_assignment" "funcapp_storage_blob" {
  scope                = azurerm_storage_account.main.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = var.funcapp_principal_id
}

# RBAC: Grant Function App access to queues (for triggers)
resource "azurerm_role_assignment" "funcapp_storage_queue" {
  scope                = azurerm_storage_account.main.id
  role_definition_name = "Storage Queue Data Contributor"
  principal_id         = var.funcapp_principal_id
}

# RBAC: Grant Function App access to tables
resource "azurerm_role_assignment" "funcapp_storage_table" {
  scope                = azurerm_storage_account.main.id
  role_definition_name = "Storage Table Data Contributor"
  principal_id         = var.funcapp_principal_id
}
```

### 3.3 Function App Configuration for Storage

**File: `modules/app/main.tf`** (Updated Function App)

```hcl
resource "azurerm_linux_function_app" "orchestrator" {
  name                       = "func-PULSE-${var.project_name}-orchestrator-${var.environment}"
  location                   = var.location
  resource_group_name        = var.resource_group_name
  service_plan_id            = azurerm_service_plan.main.id

  # SECURITY: Use managed identity instead of storage key
  storage_account_name       = var.storage_account_name
  storage_uses_managed_identity = true  # KEY CHANGE

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

    # Storage - Managed Identity configuration
    # NOTE: When using managed identity, use account name format
    "AzureWebJobsStorage__accountName" = var.storage_account_name
    # The above replaces connection string completely

    # For custom blob operations
    "STORAGE_ACCOUNT_NAME"           = var.storage_account_name
    "STORAGE_USE_MANAGED_IDENTITY"   = "true"

    # ... other settings ...
  }

  virtual_network_subnet_id = var.app_subnet_id
  tags = var.tags
}
```

### 3.4 Python Code for Managed Identity Storage Access

**File: `orchestrator/shared_code/blob_managed.py`** (New file)

```python
"""
Azure Blob Storage client using Managed Identity.

This module provides secure blob storage access without credentials
by leveraging Azure Managed Identity and DefaultAzureCredential.
"""

import os
import logging
from functools import lru_cache
from typing import Optional, BinaryIO, Union
from datetime import datetime, timedelta

from azure.identity import DefaultAzureCredential, ManagedIdentityCredential
from azure.storage.blob import (
    BlobServiceClient,
    ContainerClient,
    BlobClient,
    generate_blob_sas,
    BlobSasPermissions,
    ContentSettings,
)
from azure.core.exceptions import ResourceNotFoundError, ResourceExistsError

logger = logging.getLogger(__name__)


class BlobStorageManager:
    """
    Manages Azure Blob Storage operations using Managed Identity.

    This class provides a secure interface to Azure Blob Storage
    without requiring connection strings or access keys.
    """

    def __init__(
        self,
        account_name: Optional[str] = None,
        use_managed_identity: bool = True,
    ):
        """
        Initialize the Blob Storage Manager.

        Args:
            account_name: Storage account name. If not provided, reads from
                         STORAGE_ACCOUNT_NAME environment variable.
            use_managed_identity: If True, uses managed identity. If False,
                                 falls back to connection string (for local dev).
        """
        self.account_name = account_name or os.environ.get("STORAGE_ACCOUNT_NAME")
        self.use_managed_identity = use_managed_identity

        if not self.account_name:
            raise ValueError(
                "Storage account name is required. "
                "Set STORAGE_ACCOUNT_NAME environment variable."
            )

        self._service_client: Optional[BlobServiceClient] = None
        self._credential: Optional[DefaultAzureCredential] = None

    @property
    def credential(self) -> DefaultAzureCredential:
        """Get or create the Azure credential."""
        if self._credential is None:
            self._credential = DefaultAzureCredential(
                # Exclude interactive methods in production
                exclude_interactive_browser_credential=True,
                exclude_shared_token_cache_credential=True,
            )
        return self._credential

    @property
    def service_client(self) -> BlobServiceClient:
        """Get or create the BlobServiceClient."""
        if self._service_client is None:
            if self.use_managed_identity:
                account_url = f"https://{self.account_name}.blob.core.windows.net"
                self._service_client = BlobServiceClient(
                    account_url=account_url,
                    credential=self.credential,
                )
                logger.info(
                    f"Initialized BlobServiceClient with managed identity "
                    f"for account: {self.account_name}"
                )
            else:
                # Fallback for local development
                connection_string = self._get_connection_string()
                if connection_string:
                    self._service_client = BlobServiceClient.from_connection_string(
                        connection_string
                    )
                    logger.warning(
                        "Using connection string for blob storage. "
                        "Consider using managed identity in production."
                    )
                else:
                    raise ValueError(
                        "No connection string available and managed identity disabled."
                    )

        return self._service_client

    def _get_connection_string(self) -> Optional[str]:
        """Get connection string from environment (for local dev only)."""
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

    def get_container_client(self, container_name: str) -> ContainerClient:
        """
        Get a ContainerClient for the specified container.

        Args:
            container_name: Name of the blob container

        Returns:
            ContainerClient instance
        """
        return self.service_client.get_container_client(container_name)

    def get_blob_client(
        self, container_name: str, blob_name: str
    ) -> BlobClient:
        """
        Get a BlobClient for the specified blob.

        Args:
            container_name: Name of the blob container
            blob_name: Name/path of the blob

        Returns:
            BlobClient instance
        """
        container = self.get_container_client(container_name)
        return container.get_blob_client(blob_name)

    def upload_blob(
        self,
        container_name: str,
        blob_name: str,
        data: Union[bytes, BinaryIO, str],
        overwrite: bool = True,
        content_type: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> str:
        """
        Upload data to a blob.

        Args:
            container_name: Target container
            blob_name: Name/path of the blob
            data: Data to upload (bytes, file-like object, or string)
            overwrite: Whether to overwrite existing blob
            content_type: MIME type of the content
            metadata: Custom metadata dictionary

        Returns:
            Blob URL
        """
        blob_client = self.get_blob_client(container_name, blob_name)

        content_settings = None
        if content_type:
            content_settings = ContentSettings(content_type=content_type)

        # Convert string to bytes if needed
        if isinstance(data, str):
            data = data.encode("utf-8")

        blob_client.upload_blob(
            data,
            overwrite=overwrite,
            content_settings=content_settings,
            metadata=metadata,
        )

        logger.info(f"Uploaded blob: {container_name}/{blob_name}")
        return blob_client.url

    def download_blob(
        self, container_name: str, blob_name: str
    ) -> bytes:
        """
        Download a blob's contents.

        Args:
            container_name: Source container
            blob_name: Name/path of the blob

        Returns:
            Blob contents as bytes

        Raises:
            ResourceNotFoundError: If blob doesn't exist
        """
        blob_client = self.get_blob_client(container_name, blob_name)
        return blob_client.download_blob().readall()

    def download_blob_to_text(
        self, container_name: str, blob_name: str, encoding: str = "utf-8"
    ) -> str:
        """
        Download a blob as text.

        Args:
            container_name: Source container
            blob_name: Name/path of the blob
            encoding: Text encoding (default: utf-8)

        Returns:
            Blob contents as string
        """
        data = self.download_blob(container_name, blob_name)
        return data.decode(encoding)

    def delete_blob(
        self, container_name: str, blob_name: str, soft_delete: bool = True
    ) -> None:
        """
        Delete a blob.

        Args:
            container_name: Container name
            blob_name: Blob name/path
            soft_delete: If True, uses soft delete (recoverable)
        """
        blob_client = self.get_blob_client(container_name, blob_name)
        blob_client.delete_blob()
        logger.info(f"Deleted blob: {container_name}/{blob_name}")

    def blob_exists(self, container_name: str, blob_name: str) -> bool:
        """
        Check if a blob exists.

        Args:
            container_name: Container name
            blob_name: Blob name/path

        Returns:
            True if blob exists, False otherwise
        """
        blob_client = self.get_blob_client(container_name, blob_name)
        return blob_client.exists()

    def list_blobs(
        self,
        container_name: str,
        prefix: Optional[str] = None,
        max_results: Optional[int] = None,
    ) -> list:
        """
        List blobs in a container.

        Args:
            container_name: Container name
            prefix: Filter blobs by prefix
            max_results: Maximum number of results

        Returns:
            List of blob properties
        """
        container = self.get_container_client(container_name)
        blobs = container.list_blobs(name_starts_with=prefix)

        if max_results:
            return list(blobs)[:max_results]
        return list(blobs)

    def ensure_container_exists(self, container_name: str) -> None:
        """
        Create container if it doesn't exist.

        Args:
            container_name: Container name to create
        """
        container = self.get_container_client(container_name)
        try:
            container.create_container()
            logger.info(f"Created container: {container_name}")
        except ResourceExistsError:
            logger.debug(f"Container already exists: {container_name}")


# Module-level singleton for convenience
_storage_manager: Optional[BlobStorageManager] = None


def get_storage_manager() -> BlobStorageManager:
    """
    Get the singleton BlobStorageManager instance.

    Returns:
        BlobStorageManager configured from environment
    """
    global _storage_manager

    if _storage_manager is None:
        use_mi = os.environ.get("STORAGE_USE_MANAGED_IDENTITY", "true").lower() == "true"
        _storage_manager = BlobStorageManager(use_managed_identity=use_mi)

    return _storage_manager


# Convenience functions for common operations
def upload_blob(
    container_name: str,
    blob_name: str,
    data: Union[bytes, BinaryIO, str],
    **kwargs,
) -> str:
    """Upload data to a blob using the default storage manager."""
    return get_storage_manager().upload_blob(container_name, blob_name, data, **kwargs)


def download_blob(container_name: str, blob_name: str) -> bytes:
    """Download a blob using the default storage manager."""
    return get_storage_manager().download_blob(container_name, blob_name)


def download_blob_text(
    container_name: str, blob_name: str, encoding: str = "utf-8"
) -> str:
    """Download a blob as text using the default storage manager."""
    return get_storage_manager().download_blob_to_text(
        container_name, blob_name, encoding
    )
```

---

## 4. Azure OpenAI with Managed Identity

### 4.1 Required RBAC Roles

| Role | Scope | Purpose |
|------|-------|---------|
| `Cognitive Services OpenAI User` | OpenAI Account | Use models (chat, completions) |
| `Cognitive Services OpenAI Contributor` | OpenAI Account | Manage deployments |

### 4.2 Terraform Configuration

**File: `modules/openai/main.tf`** (Add RBAC)

```hcl
# RBAC: Grant Web App access to OpenAI
resource "azurerm_role_assignment" "webapp_openai" {
  scope                = azurerm_cognitive_account.openai.id
  role_definition_name = "Cognitive Services OpenAI User"
  principal_id         = var.webapp_principal_id
}

# RBAC: Grant Function App access to OpenAI
resource "azurerm_role_assignment" "funcapp_openai" {
  scope                = azurerm_cognitive_account.openai.id
  role_definition_name = "Cognitive Services OpenAI User"
  principal_id         = var.funcapp_principal_id
}
```

### 4.3 Python Code for Managed Identity OpenAI Access

**File: `orchestrator/shared_code/openai_managed.py`** (New file)

```python
"""
Azure OpenAI client using Managed Identity.

This module provides secure OpenAI access without API keys
by leveraging Azure Managed Identity and DefaultAzureCredential.
"""

import os
import logging
from functools import lru_cache
from typing import Optional, Generator, Any

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI

logger = logging.getLogger(__name__)


class OpenAIManager:
    """
    Manages Azure OpenAI operations using Managed Identity.

    This class provides a secure interface to Azure OpenAI
    without requiring API keys.
    """

    # Azure OpenAI token scope
    COGNITIVE_SERVICES_SCOPE = "https://cognitiveservices.azure.com/.default"

    def __init__(
        self,
        endpoint: Optional[str] = None,
        api_version: Optional[str] = None,
        use_managed_identity: bool = True,
    ):
        """
        Initialize the OpenAI Manager.

        Args:
            endpoint: Azure OpenAI endpoint URL. If not provided, reads from
                     OPENAI_ENDPOINT environment variable.
            api_version: API version string. If not provided, reads from
                        OPENAI_API_VERSION or defaults to latest.
            use_managed_identity: If True, uses managed identity. If False,
                                 uses API key from environment.
        """
        self.endpoint = endpoint or os.environ.get("OPENAI_ENDPOINT")
        self.api_version = api_version or os.environ.get(
            "OPENAI_API_VERSION", "2024-02-15-preview"
        )
        self.use_managed_identity = use_managed_identity

        if not self.endpoint:
            raise ValueError(
                "OpenAI endpoint is required. "
                "Set OPENAI_ENDPOINT environment variable."
            )

        self._client: Optional[AzureOpenAI] = None
        self._credential: Optional[DefaultAzureCredential] = None

    @property
    def credential(self) -> DefaultAzureCredential:
        """Get or create the Azure credential."""
        if self._credential is None:
            self._credential = DefaultAzureCredential(
                exclude_interactive_browser_credential=True,
                exclude_shared_token_cache_credential=True,
            )
        return self._credential

    @property
    def client(self) -> AzureOpenAI:
        """Get or create the AzureOpenAI client."""
        if self._client is None:
            if self.use_managed_identity:
                # Create token provider for Azure AD authentication
                token_provider = get_bearer_token_provider(
                    self.credential,
                    self.COGNITIVE_SERVICES_SCOPE,
                )

                self._client = AzureOpenAI(
                    azure_endpoint=self.endpoint,
                    api_version=self.api_version,
                    azure_ad_token_provider=token_provider,
                )
                logger.info(
                    f"Initialized AzureOpenAI with managed identity "
                    f"for endpoint: {self.endpoint}"
                )
            else:
                # Fallback to API key
                api_key = os.environ.get("AZURE_OPENAI_API_KEY")
                if not api_key:
                    raise ValueError(
                        "AZURE_OPENAI_API_KEY not set and managed identity disabled."
                    )

                self._client = AzureOpenAI(
                    azure_endpoint=self.endpoint,
                    api_version=self.api_version,
                    api_key=api_key,
                )
                logger.warning(
                    "Using API key for OpenAI authentication. "
                    "Consider using managed identity in production."
                )

        return self._client

    def get_deployment_name(self, deployment_type: str) -> str:
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

    def chat_completion(
        self,
        messages: list[dict],
        deployment_type: str = "chat",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        **kwargs,
    ) -> Any:
        """
        Create a chat completion.

        Args:
            messages: List of message dictionaries with 'role' and 'content'
            deployment_type: Type of deployment to use
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens in response
            stream: Whether to stream the response
            **kwargs: Additional parameters for the API

        Returns:
            ChatCompletion response or stream
        """
        deployment = self.get_deployment_name(deployment_type)

        return self.client.chat.completions.create(
            model=deployment,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=stream,
            **kwargs,
        )

    def chat_completion_stream(
        self,
        messages: list[dict],
        deployment_type: str = "chat",
        **kwargs,
    ) -> Generator[str, None, None]:
        """
        Create a streaming chat completion and yield content chunks.

        Args:
            messages: List of message dictionaries
            deployment_type: Type of deployment to use
            **kwargs: Additional parameters

        Yields:
            Content chunks from the response
        """
        response = self.chat_completion(
            messages=messages,
            deployment_type=deployment_type,
            stream=True,
            **kwargs,
        )

        for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def transcribe_audio(
        self,
        audio_file: bytes,
        language: Optional[str] = None,
        prompt: Optional[str] = None,
    ) -> str:
        """
        Transcribe audio using Whisper.

        Args:
            audio_file: Audio file bytes
            language: Optional language hint (ISO 639-1)
            prompt: Optional prompt to guide transcription

        Returns:
            Transcribed text
        """
        deployment = self.get_deployment_name("whisper")

        # Create a file-like object for the API
        import io
        audio_buffer = io.BytesIO(audio_file)
        audio_buffer.name = "audio.wav"

        response = self.client.audio.transcriptions.create(
            model=deployment,
            file=audio_buffer,
            language=language,
            prompt=prompt,
        )

        return response.text


# Module-level singleton
_openai_manager: Optional[OpenAIManager] = None


def get_openai_manager() -> OpenAIManager:
    """
    Get the singleton OpenAIManager instance.

    Returns:
        OpenAIManager configured from environment
    """
    global _openai_manager

    if _openai_manager is None:
        use_mi = os.environ.get(
            "OPENAI_USE_MANAGED_IDENTITY", "true"
        ).lower() == "true"
        _openai_manager = OpenAIManager(use_managed_identity=use_mi)

    return _openai_manager


# Convenience functions
def chat_completion(messages: list[dict], **kwargs) -> Any:
    """Create a chat completion using the default manager."""
    return get_openai_manager().chat_completion(messages, **kwargs)


def chat_stream(messages: list[dict], **kwargs) -> Generator[str, None, None]:
    """Create a streaming chat completion using the default manager."""
    return get_openai_manager().chat_completion_stream(messages, **kwargs)
```

---

## 5. Azure PostgreSQL with Managed Identity

### 5.1 Enable Azure AD Authentication on PostgreSQL

Azure Database for PostgreSQL Flexible Server supports Azure AD authentication,
allowing applications to connect using managed identity instead of passwords.

### 5.2 Terraform Configuration

**File: `modules/analytics_postgres/main.tf`** (Updated)

```hcl
resource "azurerm_postgresql_flexible_server" "main" {
  name                   = "pg-PULSE-analytics-${var.environment}"
  resource_group_name    = var.resource_group_name
  location               = var.location
  version                = "16"
  delegated_subnet_id    = var.delegated_subnet_id
  private_dns_zone_id    = azurerm_private_dns_zone.postgres.id

  # Still need an admin for initial setup
  administrator_login    = var.admin_username
  administrator_password = var.admin_password

  storage_mb             = 32768
  sku_name               = "B_Standard_B1ms"
  zone                   = "1"

  # Enable Azure AD authentication
  authentication {
    active_directory_auth_enabled = true
    password_auth_enabled         = true  # Keep password auth for migrations
    tenant_id                     = var.tenant_id
  }

  tags = var.tags
}

# Create Azure AD admin for the PostgreSQL server
resource "azurerm_postgresql_flexible_server_active_directory_administrator" "main" {
  server_name         = azurerm_postgresql_flexible_server.main.name
  resource_group_name = var.resource_group_name
  tenant_id           = var.tenant_id
  object_id           = var.aad_admin_object_id
  principal_name      = var.aad_admin_principal_name
  principal_type      = "Group"  # or "User" or "ServicePrincipal"
}
```

### 5.3 Python Code for Managed Identity PostgreSQL Access

**File: `orchestrator/shared_code/postgres_managed.py`** (New file)

```python
"""
Azure PostgreSQL client using Managed Identity.

This module provides secure PostgreSQL access without passwords
by leveraging Azure Managed Identity and Azure AD authentication.
"""

import os
import logging
from functools import lru_cache
from typing import Optional, Any
from contextlib import contextmanager

import psycopg2
from psycopg2 import pool
from azure.identity import DefaultAzureCredential

logger = logging.getLogger(__name__)


class PostgresManager:
    """
    Manages PostgreSQL connections using Managed Identity.

    This class provides a secure interface to PostgreSQL
    without requiring passwords in connection strings.
    """

    # Azure PostgreSQL token scope
    POSTGRES_SCOPE = "https://ossrdbms-aad.database.windows.net/.default"

    def __init__(
        self,
        host: Optional[str] = None,
        database: Optional[str] = None,
        user: Optional[str] = None,
        port: int = 5432,
        use_managed_identity: bool = True,
        min_connections: int = 1,
        max_connections: int = 10,
    ):
        """
        Initialize the PostgreSQL Manager.

        Args:
            host: PostgreSQL server hostname
            database: Database name
            user: Username (for managed identity, use the identity name)
            port: PostgreSQL port (default: 5432)
            use_managed_identity: If True, uses managed identity for auth
            min_connections: Minimum connections in pool
            max_connections: Maximum connections in pool
        """
        self.host = host or os.environ.get("PULSE_ANALYTICS_DB_HOST")
        self.database = database or os.environ.get(
            "PULSE_ANALYTICS_DB_NAME", "pulse_analytics"
        )
        self.user = user or os.environ.get("PULSE_ANALYTICS_DB_USER")
        self.port = port or int(os.environ.get("PULSE_ANALYTICS_DB_PORT", "5432"))
        self.use_managed_identity = use_managed_identity
        self.min_connections = min_connections
        self.max_connections = max_connections

        if not all([self.host, self.database, self.user]):
            raise ValueError(
                "Database configuration incomplete. Required: host, database, user. "
                "Set PULSE_ANALYTICS_DB_HOST, PULSE_ANALYTICS_DB_NAME, PULSE_ANALYTICS_DB_USER."
            )

        self._pool: Optional[pool.ThreadedConnectionPool] = None
        self._credential: Optional[DefaultAzureCredential] = None

    @property
    def credential(self) -> DefaultAzureCredential:
        """Get or create the Azure credential."""
        if self._credential is None:
            self._credential = DefaultAzureCredential(
                exclude_interactive_browser_credential=True,
                exclude_shared_token_cache_credential=True,
            )
        return self._credential

    def _get_access_token(self) -> str:
        """
        Get an Azure AD access token for PostgreSQL.

        Returns:
            Access token string to use as password
        """
        token = self.credential.get_token(self.POSTGRES_SCOPE)
        return token.token

    def _get_connection_params(self) -> dict:
        """
        Build connection parameters.

        Returns:
            Dictionary of psycopg2 connection parameters
        """
        params = {
            "host": self.host,
            "port": self.port,
            "database": self.database,
            "user": self.user,
            "sslmode": "require",
            "connect_timeout": 10,
        }

        if self.use_managed_identity:
            # Use Azure AD token as password
            params["password"] = self._get_access_token()
            logger.debug("Using managed identity token for PostgreSQL authentication")
        else:
            # Fall back to password from environment
            password = os.environ.get("PULSE_ANALYTICS_DB_PASSWORD")
            if not password:
                raise ValueError(
                    "PULSE_ANALYTICS_DB_PASSWORD not set and managed identity disabled."
                )
            params["password"] = password
            logger.warning(
                "Using password authentication for PostgreSQL. "
                "Consider using managed identity in production."
            )

        return params

    def get_pool(self) -> pool.ThreadedConnectionPool:
        """
        Get or create the connection pool.

        Note: When using managed identity, tokens expire (typically 1 hour).
        For long-running applications, consider refreshing the pool periodically.

        Returns:
            ThreadedConnectionPool instance
        """
        if self._pool is None:
            params = self._get_connection_params()
            self._pool = pool.ThreadedConnectionPool(
                self.min_connections,
                self.max_connections,
                **params,
            )
            logger.info(
                f"Created PostgreSQL connection pool for {self.host}/{self.database}"
            )

        return self._pool

    def refresh_pool(self) -> None:
        """
        Refresh the connection pool with a new token.

        Call this periodically for long-running applications
        to handle token expiration.
        """
        if self._pool:
            self._pool.closeall()
            self._pool = None
            logger.info("Closed existing PostgreSQL connection pool")

        # Force new token acquisition
        self._credential = None

        # Create new pool
        self.get_pool()
        logger.info("Refreshed PostgreSQL connection pool with new token")

    @contextmanager
    def get_connection(self):
        """
        Context manager for database connections.

        Automatically returns connection to pool when done.

        Usage:
            with manager.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
        """
        conn = self.get_pool().getconn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self.get_pool().putconn(conn)

    def execute_query(
        self,
        query: str,
        params: Optional[tuple] = None,
        fetch: bool = True,
    ) -> Optional[list]:
        """
        Execute a query and optionally fetch results.

        Args:
            query: SQL query string
            params: Query parameters (for parameterized queries)
            fetch: Whether to fetch and return results

        Returns:
            List of result tuples if fetch=True, None otherwise
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                if fetch:
                    return cur.fetchall()
                return None

    def execute_many(
        self,
        query: str,
        params_list: list[tuple],
    ) -> int:
        """
        Execute a query with multiple parameter sets.

        Args:
            query: SQL query string with placeholders
            params_list: List of parameter tuples

        Returns:
            Number of rows affected
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.executemany(query, params_list)
                return cur.rowcount

    def close(self) -> None:
        """Close all connections in the pool."""
        if self._pool:
            self._pool.closeall()
            self._pool = None
            logger.info("Closed PostgreSQL connection pool")


# Module-level singleton
_postgres_manager: Optional[PostgresManager] = None


def get_postgres_manager() -> PostgresManager:
    """
    Get the singleton PostgresManager instance.

    Returns:
        PostgresManager configured from environment
    """
    global _postgres_manager

    if _postgres_manager is None:
        use_mi = os.environ.get(
            "POSTGRES_USE_MANAGED_IDENTITY", "true"
        ).lower() == "true"
        _postgres_manager = PostgresManager(use_managed_identity=use_mi)

    return _postgres_manager


@contextmanager
def get_db_connection():
    """
    Convenience context manager for database connections.

    Usage:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM users")
    """
    manager = get_postgres_manager()
    with manager.get_connection() as conn:
        yield conn
```

---

## 6. Azure Key Vault with Managed Identity

### 6.1 Required RBAC Roles

| Role | Scope | Purpose |
|------|-------|---------|
| `Key Vault Secrets User` | Key Vault | Read secrets |
| `Key Vault Secrets Officer` | Key Vault | Manage secrets |
| `Key Vault Crypto User` | Key Vault | Cryptographic operations |
| `Key Vault Certificates User` | Key Vault | Read certificates |

### 6.2 Python Code for Key Vault Access

**File: `orchestrator/shared_code/keyvault_managed.py`** (New file)

```python
"""
Azure Key Vault client using Managed Identity.

This module provides secure secret access from Key Vault
without requiring client credentials.
"""

import os
import logging
from functools import lru_cache
from typing import Optional

from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

logger = logging.getLogger(__name__)


class KeyVaultManager:
    """
    Manages Azure Key Vault operations using Managed Identity.
    """

    def __init__(self, vault_url: Optional[str] = None):
        """
        Initialize the Key Vault Manager.

        Args:
            vault_url: Key Vault URL (https://<name>.vault.azure.net)
        """
        self.vault_url = vault_url or os.environ.get("AZURE_KEYVAULT_URI")

        if not self.vault_url:
            raise ValueError(
                "Key Vault URL is required. "
                "Set AZURE_KEYVAULT_URI environment variable."
            )

        self._client: Optional[SecretClient] = None
        self._credential: Optional[DefaultAzureCredential] = None

    @property
    def credential(self) -> DefaultAzureCredential:
        """Get or create the Azure credential."""
        if self._credential is None:
            self._credential = DefaultAzureCredential(
                exclude_interactive_browser_credential=True,
                exclude_shared_token_cache_credential=True,
            )
        return self._credential

    @property
    def client(self) -> SecretClient:
        """Get or create the SecretClient."""
        if self._client is None:
            self._client = SecretClient(
                vault_url=self.vault_url,
                credential=self.credential,
            )
            logger.info(f"Initialized Key Vault client for: {self.vault_url}")

        return self._client

    def get_secret(self, name: str) -> Optional[str]:
        """
        Get a secret value from Key Vault.

        Args:
            name: Secret name

        Returns:
            Secret value or None if not found
        """
        try:
            secret = self.client.get_secret(name)
            return secret.value
        except Exception as e:
            logger.warning(f"Failed to get secret '{name}': {e}")
            return None

    def set_secret(
        self,
        name: str,
        value: str,
        content_type: Optional[str] = None,
        tags: Optional[dict] = None,
    ) -> None:
        """
        Set a secret value in Key Vault.

        Args:
            name: Secret name
            value: Secret value
            content_type: MIME type of the secret
            tags: Custom tags
        """
        self.client.set_secret(
            name,
            value,
            content_type=content_type,
            tags=tags,
        )
        logger.info(f"Set secret: {name}")

    def delete_secret(self, name: str) -> None:
        """
        Delete a secret from Key Vault.

        Args:
            name: Secret name
        """
        poller = self.client.begin_delete_secret(name)
        poller.result()
        logger.info(f"Deleted secret: {name}")

    def list_secrets(self) -> list[str]:
        """
        List all secret names in Key Vault.

        Returns:
            List of secret names
        """
        return [s.name for s in self.client.list_properties_of_secrets()]


# Module-level singleton
_keyvault_manager: Optional[KeyVaultManager] = None


def get_keyvault_manager() -> Optional[KeyVaultManager]:
    """Get the singleton KeyVaultManager instance."""
    global _keyvault_manager

    if _keyvault_manager is None:
        vault_url = os.environ.get("AZURE_KEYVAULT_URI")
        if vault_url:
            _keyvault_manager = KeyVaultManager(vault_url)
        else:
            logger.warning("AZURE_KEYVAULT_URI not set - Key Vault disabled")
            return None

    return _keyvault_manager


def get_secret(name: str, default: Optional[str] = None) -> Optional[str]:
    """
    Get a secret from Key Vault with fallback.

    Args:
        name: Secret name
        default: Default value if secret not found

    Returns:
        Secret value or default
    """
    manager = get_keyvault_manager()
    if manager:
        value = manager.get_secret(name)
        if value:
            return value

    # Fall back to environment variable
    env_name = name.upper().replace("-", "_")
    return os.environ.get(env_name, default)
```

---

## 7. SAS Token Implementation

For scenarios where managed identity isn't available (e.g., external client access),
use **Shared Access Signatures (SAS)** with minimal scope and time limits.

### 7.1 Types of SAS Tokens

| Type | Scope | Use Case |
|------|-------|----------|
| **User Delegation SAS** | Uses Azure AD credentials | Most secure, recommended |
| **Service SAS** | Single resource (blob, queue, etc.) | Specific resource access |
| **Account SAS** | Entire storage account | Broad access, use sparingly |

### 7.2 Generating User Delegation SAS (Recommended)

**File: `orchestrator/shared_code/sas_generator.py`**

```python
"""
SAS Token Generator using User Delegation.

User delegation SAS is more secure than account-key SAS because:
1. It uses Azure AD credentials (no storage keys exposed)
2. Tokens are tied to the user/identity that created them
3. Easier to audit and revoke
"""

import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from azure.identity import DefaultAzureCredential
from azure.storage.blob import (
    BlobServiceClient,
    generate_blob_sas,
    generate_container_sas,
    BlobSasPermissions,
    ContainerSasPermissions,
    UserDelegationKey,
)

logger = logging.getLogger(__name__)


class SASGenerator:
    """
    Generates SAS tokens using user delegation (Azure AD).
    """

    def __init__(self, account_name: Optional[str] = None):
        """
        Initialize the SAS Generator.

        Args:
            account_name: Storage account name
        """
        self.account_name = account_name or os.environ.get("STORAGE_ACCOUNT_NAME")

        if not self.account_name:
            raise ValueError("Storage account name is required")

        self.account_url = f"https://{self.account_name}.blob.core.windows.net"
        self._credential = DefaultAzureCredential()
        self._service_client = BlobServiceClient(
            account_url=self.account_url,
            credential=self._credential,
        )
        self._delegation_key: Optional[UserDelegationKey] = None
        self._delegation_key_expiry: Optional[datetime] = None

    def _get_user_delegation_key(
        self, validity_hours: int = 1
    ) -> UserDelegationKey:
        """
        Get or refresh the user delegation key.

        Args:
            validity_hours: How long the key should be valid

        Returns:
            UserDelegationKey for signing SAS tokens
        """
        now = datetime.now(timezone.utc)

        # Check if we need a new key
        if (
            self._delegation_key is None
            or self._delegation_key_expiry is None
            or now >= self._delegation_key_expiry - timedelta(minutes=5)
        ):
            start_time = now - timedelta(minutes=5)  # Allow for clock skew
            expiry_time = now + timedelta(hours=validity_hours)

            self._delegation_key = self._service_client.get_user_delegation_key(
                key_start_time=start_time,
                key_expiry_time=expiry_time,
            )
            self._delegation_key_expiry = expiry_time
            logger.debug("Obtained new user delegation key")

        return self._delegation_key

    def generate_blob_sas_url(
        self,
        container_name: str,
        blob_name: str,
        permission: str = "r",
        expiry_minutes: int = 60,
        content_disposition: Optional[str] = None,
        content_type: Optional[str] = None,
    ) -> str:
        """
        Generate a SAS URL for a specific blob.

        Args:
            container_name: Container name
            blob_name: Blob name/path
            permission: Permission string (r=read, w=write, d=delete, etc.)
            expiry_minutes: Token validity in minutes
            content_disposition: Override content-disposition header
            content_type: Override content-type header

        Returns:
            Full SAS URL for the blob
        """
        delegation_key = self._get_user_delegation_key()

        # Parse permission string
        permissions = BlobSasPermissions(
            read="r" in permission,
            write="w" in permission,
            delete="d" in permission,
            add="a" in permission,
            create="c" in permission,
        )

        now = datetime.now(timezone.utc)
        expiry = now + timedelta(minutes=expiry_minutes)

        sas_token = generate_blob_sas(
            account_name=self.account_name,
            container_name=container_name,
            blob_name=blob_name,
            user_delegation_key=delegation_key,
            permission=permissions,
            expiry=expiry,
            start=now - timedelta(minutes=5),
            content_disposition=content_disposition,
            content_type=content_type,
        )

        url = f"{self.account_url}/{container_name}/{blob_name}?{sas_token}"
        logger.debug(
            f"Generated SAS URL for {container_name}/{blob_name} "
            f"(expires in {expiry_minutes} minutes)"
        )

        return url

    def generate_container_sas_url(
        self,
        container_name: str,
        permission: str = "rl",
        expiry_minutes: int = 60,
    ) -> str:
        """
        Generate a SAS URL for a container (list and read blobs).

        Args:
            container_name: Container name
            permission: Permission string (r=read, l=list, w=write, d=delete)
            expiry_minutes: Token validity in minutes

        Returns:
            Container SAS URL with token
        """
        delegation_key = self._get_user_delegation_key()

        permissions = ContainerSasPermissions(
            read="r" in permission,
            list="l" in permission,
            write="w" in permission,
            delete="d" in permission,
        )

        now = datetime.now(timezone.utc)
        expiry = now + timedelta(minutes=expiry_minutes)

        sas_token = generate_container_sas(
            account_name=self.account_name,
            container_name=container_name,
            user_delegation_key=delegation_key,
            permission=permissions,
            expiry=expiry,
            start=now - timedelta(minutes=5),
        )

        url = f"{self.account_url}/{container_name}?{sas_token}"
        logger.debug(
            f"Generated container SAS URL for {container_name} "
            f"(expires in {expiry_minutes} minutes)"
        )

        return url


# Convenience function
def get_blob_download_url(
    container_name: str,
    blob_name: str,
    expiry_minutes: int = 60,
) -> str:
    """
    Get a temporary download URL for a blob.

    Args:
        container_name: Container name
        blob_name: Blob name/path
        expiry_minutes: How long the URL should be valid

    Returns:
        SAS URL for downloading the blob
    """
    generator = SASGenerator()
    return generator.generate_blob_sas_url(
        container_name=container_name,
        blob_name=blob_name,
        permission="r",
        expiry_minutes=expiry_minutes,
    )


def get_blob_upload_url(
    container_name: str,
    blob_name: str,
    expiry_minutes: int = 30,
) -> str:
    """
    Get a temporary upload URL for a blob.

    Args:
        container_name: Container name
        blob_name: Blob name/path
        expiry_minutes: How long the URL should be valid

    Returns:
        SAS URL for uploading to the blob
    """
    generator = SASGenerator()
    return generator.generate_blob_sas_url(
        container_name=container_name,
        blob_name=blob_name,
        permission="cw",  # create + write
        expiry_minutes=expiry_minutes,
    )
```

### 7.3 SAS Token Best Practices

| Practice | Description |
|----------|-------------|
| **Use User Delegation SAS** | More secure than account-key SAS |
| **Minimal Permissions** | Only grant permissions needed (read-only when possible) |
| **Short Expiry** | Keep tokens short-lived (minutes to hours, not days) |
| **HTTPS Only** | Generate SAS with `protocol="https"` |
| **Specific Resources** | Prefer blob-level SAS over container or account SAS |
| **Audit Access** | Monitor SAS usage via Storage Analytics |

---

## 8. Terraform Infrastructure Changes

### 8.1 Complete Updated main.tf

**File: `main.tf`** (Key additions)

```hcl
# Ensure managed identities are created first
resource "azurerm_linux_web_app" "ui" {
  # ... existing config ...

  identity {
    type = "SystemAssigned"
  }
}

resource "azurerm_linux_function_app" "orchestrator" {
  # ... existing config ...

  identity {
    type = "SystemAssigned"
  }

  # Use managed identity for storage
  storage_uses_managed_identity = true
}

# ============================================
# RBAC Assignments for Managed Identities
# ============================================

# Storage RBAC
module "storage_rbac" {
  source = "./modules/rbac/storage"

  storage_account_id    = module.storage.id
  webapp_principal_id   = azurerm_linux_web_app.ui.identity[0].principal_id
  funcapp_principal_id  = azurerm_linux_function_app.orchestrator.identity[0].principal_id
}

# OpenAI RBAC
module "openai_rbac" {
  source = "./modules/rbac/openai"

  openai_account_id     = module.openai.id
  webapp_principal_id   = azurerm_linux_web_app.ui.identity[0].principal_id
  funcapp_principal_id  = azurerm_linux_function_app.orchestrator.identity[0].principal_id
}

# Key Vault RBAC
module "keyvault_rbac" {
  source = "./modules/rbac/keyvault"

  keyvault_id           = module.keyvault.id
  webapp_principal_id   = azurerm_linux_web_app.ui.identity[0].principal_id
  funcapp_principal_id  = azurerm_linux_function_app.orchestrator.identity[0].principal_id
}
```

### 8.2 RBAC Module for Storage

**File: `modules/rbac/storage/main.tf`**

```hcl
variable "storage_account_id" {
  type = string
}

variable "webapp_principal_id" {
  type = string
}

variable "funcapp_principal_id" {
  type = string
}

# Web App - Blob Data Contributor
resource "azurerm_role_assignment" "webapp_blob" {
  scope                = var.storage_account_id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = var.webapp_principal_id
}

# Function App - Blob Data Contributor
resource "azurerm_role_assignment" "funcapp_blob" {
  scope                = var.storage_account_id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = var.funcapp_principal_id
}

# Function App - Queue Data Contributor (for triggers)
resource "azurerm_role_assignment" "funcapp_queue" {
  scope                = var.storage_account_id
  role_definition_name = "Storage Queue Data Contributor"
  principal_id         = var.funcapp_principal_id
}

# Function App - Table Data Contributor
resource "azurerm_role_assignment" "funcapp_table" {
  scope                = var.storage_account_id
  role_definition_name = "Storage Table Data Contributor"
  principal_id         = var.funcapp_principal_id
}
```

### 8.3 Updated Variables for Managed Identity

**File: `variables.tf`** (Add new variables)

```hcl
variable "storage_use_managed_identity" {
  description = "Use managed identity for storage access instead of connection strings"
  type        = bool
  default     = true
}

variable "openai_use_managed_identity" {
  description = "Use managed identity for OpenAI access instead of API keys"
  type        = bool
  default     = true
}

variable "postgres_use_managed_identity" {
  description = "Use managed identity for PostgreSQL access"
  type        = bool
  default     = true
}
```

---

## 9. Application Code Changes

### 9.1 Next.js API Route Updates

**File: `ui/app/api/orchestrator/[...path]/route.ts`** (Updated)

```typescript
// No changes needed for managed identity - this runs server-side
// and calls the Function App which uses managed identity internally

// If you need to call Azure services directly from Next.js,
// use @azure/identity package:

import { DefaultAzureCredential } from "@azure/identity";
import { BlobServiceClient } from "@azure/storage-blob";

// For server-side Azure access (if needed)
async function getBlobClient() {
  const accountName = process.env.STORAGE_ACCOUNT_NAME;
  const credential = new DefaultAzureCredential();

  return new BlobServiceClient(
    `https://${accountName}.blob.core.windows.net`,
    credential
  );
}
```

### 9.2 Python Requirements Update

**File: `orchestrator/requirements.txt`** (Updated)

```text
# Azure Identity (for managed identity)
azure-identity>=1.15.0

# Azure Storage (supports managed identity)
azure-storage-blob>=12.19.0
azure-storage-queue>=12.9.0

# Azure Key Vault (supports managed identity)
azure-keyvault-secrets>=4.7.0

# Azure OpenAI SDK (supports managed identity via token provider)
openai>=1.12.0

# PostgreSQL
psycopg2-binary>=2.9.9

# Other dependencies
azure-functions>=1.17.0
```

---

## 10. CI/CD Pipeline Updates

### 10.1 GitHub Actions for Terraform with RBAC

When using managed identity, CI/CD pipelines still need service principal access
to deploy infrastructure, but the deployed applications use managed identity.

**File: `.github/workflows/deploy.yml`** (Key section)

```yaml
jobs:
  terraform:
    runs-on: ubuntu-latest
    steps:
      - name: Azure Login
        uses: azure/login@v1
        with:
          creds: ${{ secrets.AZURE_CREDENTIALS }}

      - name: Terraform Apply
        run: terraform apply -auto-approve
        env:
          ARM_CLIENT_ID: ${{ secrets.ARM_CLIENT_ID }}
          ARM_CLIENT_SECRET: ${{ secrets.ARM_CLIENT_SECRET }}
          ARM_SUBSCRIPTION_ID: ${{ secrets.AZURE_SUBSCRIPTION_ID }}
          ARM_TENANT_ID: ${{ secrets.AZURE_TENANT_ID }}

          # These are for Key Vault secrets only - apps use managed identity
          TF_VAR_azure_ad_client_secret: ${{ secrets.AZURE_AD_CLIENT_SECRET }}
          TF_VAR_nextauth_secret: ${{ secrets.NEXTAUTH_SECRET }}
```

### 10.2 Verify RBAC Assignments After Deployment

```yaml
      - name: Verify RBAC Assignments
        run: |
          # Get Web App principal ID
          WEBAPP_ID=$(az webapp identity show \
            --name app-PULSE-training-ui-${{ env.ENVIRONMENT }} \
            --resource-group rg-PULSE-training-${{ env.ENVIRONMENT }} \
            --query principalId -o tsv)

          # List role assignments
          az role assignment list \
            --assignee $WEBAPP_ID \
            --output table
```

---

## 11. Migration Checklist

### Phase 1: Preparation (Day 1)

- [ ] **Audit current authentication methods**
  - Document all connection strings in use
  - List all API keys and their locations
  - Identify all services that need RBAC grants

- [ ] **Verify managed identity is enabled**
  ```bash
  az webapp identity show --name <webapp-name> --resource-group <rg-name>
  az functionapp identity show --name <funcapp-name> --resource-group <rg-name>
  ```

### Phase 2: Infrastructure Updates (Day 2)

- [ ] **Create RBAC assignments via Terraform**
  - Storage Blob Data Contributor
  - Storage Queue Data Contributor
  - Cognitive Services OpenAI User
  - Key Vault Secrets User

- [ ] **Update storage account settings**
  ```hcl
  shared_access_key_enabled       = false
  default_to_oauth_authentication = true
  ```

- [ ] **Update Function App to use managed identity for storage**
  ```hcl
  storage_uses_managed_identity = true
  ```

### Phase 3: Application Updates (Day 3)

- [ ] **Deploy new Python modules**
  - `blob_managed.py`
  - `openai_managed.py`
  - `postgres_managed.py`
  - `keyvault_managed.py`
  - `sas_generator.py`

- [ ] **Update existing code to use new modules**
  - Replace `BlobServiceClient.from_connection_string()`
  - Replace OpenAI API key usage
  - Replace PostgreSQL password in DSN

- [ ] **Add environment variables**
  ```
  STORAGE_USE_MANAGED_IDENTITY=true
  OPENAI_USE_MANAGED_IDENTITY=true
  POSTGRES_USE_MANAGED_IDENTITY=true
  ```

### Phase 4: Testing (Day 4)

- [ ] **Test storage operations**
  - Upload blob
  - Download blob
  - List blobs
  - Generate SAS URL

- [ ] **Test OpenAI operations**
  - Chat completion
  - Audio transcription
  - Embedding generation

- [ ] **Test database operations**
  - Query execution
  - Connection pooling
  - Token refresh

### Phase 5: Cleanup (Day 5)

- [ ] **Remove old connection strings from app settings**
- [ ] **Rotate any exposed keys (they're no longer needed)**
- [ ] **Update documentation**
- [ ] **Remove legacy code paths**

---

## 12. Troubleshooting

### 12.1 "No managed identity configured"

**Symptom:** `DefaultAzureCredential` fails with no identity

**Solution:**
```bash
# Verify identity is enabled
az webapp identity show --name <app-name> --resource-group <rg>

# Enable if missing
az webapp identity assign --name <app-name> --resource-group <rg>
```

### 12.2 "AuthorizationFailed" on Storage

**Symptom:** 403 Forbidden when accessing blobs

**Solution:**
```bash
# Check RBAC assignments
az role assignment list \
  --assignee <principal-id> \
  --scope <storage-account-id>

# Grant if missing
az role assignment create \
  --role "Storage Blob Data Contributor" \
  --assignee <principal-id> \
  --scope <storage-account-id>
```

### 12.3 "Cognitive Services access denied"

**Symptom:** 401 Unauthorized when calling OpenAI

**Solution:**
```bash
# Grant OpenAI access
az role assignment create \
  --role "Cognitive Services OpenAI User" \
  --assignee <principal-id> \
  --scope <openai-account-id>
```

### 12.4 Token Expiration Issues

**Symptom:** Connections fail after ~1 hour

**Solution:** Implement token refresh:
```python
# For PostgreSQL
manager = get_postgres_manager()
manager.refresh_pool()  # Call periodically

# For long-running processes, consider using a scheduler
import schedule
schedule.every(45).minutes.do(manager.refresh_pool)
```

### 12.5 Local Development Without Managed Identity

**Solution:** Use Azure CLI authentication:
```bash
# Login to Azure CLI
az login

# Set subscription
az account set --subscription <subscription-id>

# Now DefaultAzureCredential will use CLI credentials
```

---

## Appendix A: Environment Variable Reference

| Variable | Purpose | Used By |
|----------|---------|---------|
| `STORAGE_ACCOUNT_NAME` | Storage account name | BlobStorageManager |
| `STORAGE_USE_MANAGED_IDENTITY` | Enable/disable managed identity | BlobStorageManager |
| `OPENAI_ENDPOINT` | Azure OpenAI endpoint URL | OpenAIManager |
| `OPENAI_USE_MANAGED_IDENTITY` | Enable/disable managed identity | OpenAIManager |
| `PULSE_ANALYTICS_DB_HOST` | PostgreSQL hostname | PostgresManager |
| `PULSE_ANALYTICS_DB_NAME` | Database name | PostgresManager |
| `PULSE_ANALYTICS_DB_USER` | Username (identity name) | PostgresManager |
| `POSTGRES_USE_MANAGED_IDENTITY` | Enable/disable managed identity | PostgresManager |
| `AZURE_KEYVAULT_URI` | Key Vault URL | KeyVaultManager |

---

## Appendix B: Quick Reference Commands

```bash
# List all managed identities in resource group
az identity list --resource-group <rg-name> --output table

# Get Web App managed identity details
az webapp identity show --name <app-name> --resource-group <rg-name>

# List RBAC assignments for an identity
az role assignment list --assignee <principal-id> --output table

# Create RBAC assignment
az role assignment create \
  --role "<role-name>" \
  --assignee <principal-id> \
  --scope <resource-id>

# Test managed identity authentication (from within Azure)
curl -H "Metadata: true" \
  "http://169.254.169.254/metadata/identity/oauth2/token?api-version=2018-02-01&resource=https://storage.azure.com/"

# Generate SAS token via CLI (for testing)
az storage blob generate-sas \
  --account-name <account> \
  --container-name <container> \
  --name <blob> \
  --permissions r \
  --expiry $(date -u -d "+1 hour" +%Y-%m-%dT%H:%MZ) \
  --auth-mode login \
  --as-user
```

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2024-12-25 | Security Team | Initial comprehensive guide |

---

**Next Review Date:** After initial implementation
**Classification:** RESTRICTED - Internal Use Only
