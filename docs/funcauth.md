# PULSE Function App Authentication Implementation Guide

**Version:** 1.0
**Last Updated:** 2025-12-25
**Priority:** MEDIUM
**Related Documents:** [securedbydesign.md](securedbydesign.md), [managedid.md](managedid.md), [secretsmanage.md](secretsmanage.md)

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Authentication Architecture](#authentication-architecture)
3. [Azure AD Authentication](#azure-ad-authentication)
4. [Managed Identity Authentication](#managed-identity-authentication)
5. [Function Key Authentication](#function-key-authentication)
6. [Custom JWT Validation](#custom-jwt-validation)
7. [Service-to-Service Authentication](#service-to-service-authentication)
8. [Authorization Controls](#authorization-controls)
9. [Terraform Implementation](#terraform-implementation)
10. [Testing and Validation](#testing-and-validation)
11. [Migration Checklist](#migration-checklist)

---

## Executive Summary

Azure Function App authentication is critical for securing serverless endpoints:

- **Public Functions**: Should be authenticated via Azure AD
- **Internal Functions**: Use Managed Identity for service-to-service
- **API Functions**: Validate JWTs from the web application
- **Timer Functions**: Internal only, no auth needed

This guide implements comprehensive authentication patterns for PULSE Function Apps.

---

## Authentication Architecture

### Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Authentication Flows                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐       ┌──────────────┐       ┌──────────────────────────┐ │
│  │   End User   │──────▶│   Web App    │──────▶│    Function App          │ │
│  │  (Browser)   │  JWT  │  (Next.js)   │  JWT  │  (HTTP Trigger)          │ │
│  └──────────────┘       └──────────────┘       └──────────────────────────┘ │
│                                                            │                 │
│                                                            ▼                 │
│                                               ┌──────────────────────────┐  │
│                                               │    JWT Validation        │  │
│                                               │    (Azure AD / Custom)   │  │
│                                               └──────────────────────────┘  │
│                                                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────┐                         ┌──────────────────────────┐  │
│  │    Web App       │───────────────────────▶│    Function App          │  │
│  │  (Backend)       │    Managed Identity    │  (Internal API)          │  │
│  └──────────────────┘                         └──────────────────────────┘  │
│                                                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────┐                         ┌──────────────────────────┐  │
│  │   External API   │───────────────────────▶│    Function App          │  │
│  │   (Partner)      │    API Key / OAuth     │  (Webhook Handler)       │  │
│  └──────────────────┘                         └──────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Authentication Methods Comparison

| Method | Use Case | Security Level | Complexity |
|--------|----------|----------------|------------|
| Azure AD Auth | User-facing APIs | High | Medium |
| Managed Identity | Service-to-service | High | Low |
| Function Keys | Simple API protection | Medium | Low |
| Custom JWT | Cross-system auth | High | High |
| API Key | External integrations | Medium | Low |

---

## Azure AD Authentication

### Enable Built-in Authentication

Configure via Terraform in `infra/modules/function/auth.tf`:

```hcl
# Azure Function App with Azure AD Authentication

resource "azurerm_linux_function_app" "main" {
  name                = "func-pulse-${var.environment}"
  resource_group_name = var.resource_group_name
  location            = var.location
  service_plan_id     = azurerm_service_plan.main.id

  storage_account_name       = var.storage_account_name
  storage_account_access_key = var.storage_account_key

  site_config {
    application_stack {
      python_version = "3.11"
    }

    cors {
      allowed_origins     = var.allowed_origins
      support_credentials = true
    }
  }

  auth_settings_v2 {
    auth_enabled             = true
    require_authentication   = true
    unauthenticated_action   = "Return401"
    default_provider         = "azureactivedirectory"
    require_https            = true
    runtime_version          = "~2"

    active_directory_v2 {
      client_id                  = var.azure_ad_client_id
      tenant_auth_endpoint       = "https://login.microsoftonline.com/${var.azure_ad_tenant_id}/v2.0"
      allowed_audiences          = [var.azure_ad_client_id, "api://${var.azure_ad_client_id}"]
      client_secret_setting_name = "AZURE_AD_CLIENT_SECRET"

      # Allowed groups (optional - for group-based access)
      allowed_groups = var.allowed_groups
    }

    login {
      token_store_enabled = true
    }
  }

  app_settings = {
    FUNCTIONS_WORKER_RUNTIME      = "python"
    AZURE_AD_CLIENT_ID            = var.azure_ad_client_id
    AZURE_AD_TENANT_ID            = var.azure_ad_tenant_id
    WEBSITE_AUTH_AAD_ALLOWED_TENANTS = var.azure_ad_tenant_id
  }

  identity {
    type = "SystemAssigned"
  }

  tags = var.tags
}

# App Registration for Function App
resource "azuread_application" "function_app" {
  display_name = "pulse-function-app-${var.environment}"
  owners       = [data.azuread_client_config.current.object_id]

  api {
    mapped_claims_enabled = true

    oauth2_permission_scope {
      admin_consent_description  = "Allow the application to access PULSE Function App"
      admin_consent_display_name = "Access PULSE Functions"
      enabled                    = true
      id                         = random_uuid.function_scope.result
      type                       = "User"
      user_consent_description   = "Allow the application to access PULSE Functions on your behalf"
      user_consent_display_name  = "Access PULSE Functions"
      value                      = "user_impersonation"
    }
  }

  required_resource_access {
    resource_app_id = "00000003-0000-0000-c000-000000000000" # Microsoft Graph

    resource_access {
      id   = "e1fe6dd8-ba31-4d61-89e7-88639da4683d" # User.Read
      type = "Scope"
    }
  }

  web {
    redirect_uris = ["https://${azurerm_linux_function_app.main.default_hostname}/.auth/login/aad/callback"]

    implicit_grant {
      access_token_issuance_enabled = false
      id_token_issuance_enabled     = true
    }
  }
}

resource "azuread_service_principal" "function_app" {
  client_id = azuread_application.function_app.client_id
  owners    = [data.azuread_client_config.current.object_id]
}

resource "random_uuid" "function_scope" {}
```

### Client-Side Token Acquisition

```typescript
// ui/lib/function-client.ts

import { getSession } from 'next-auth/react';

const FUNCTION_APP_URL = process.env.NEXT_PUBLIC_FUNCTION_APP_URL;

/**
 * Call Function App with Azure AD token
 */
export async function callFunction<T>(
  functionName: string,
  payload: any,
  method: 'GET' | 'POST' | 'PUT' | 'DELETE' = 'POST'
): Promise<T> {
  const session = await getSession();

  if (!session?.accessToken) {
    throw new Error('Not authenticated');
  }

  const url = `${FUNCTION_APP_URL}/api/${functionName}`;

  const response = await fetch(url, {
    method,
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${session.accessToken}`,
    },
    body: method !== 'GET' ? JSON.stringify(payload) : undefined,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: 'Unknown error' }));
    throw new Error(error.message || `Function call failed: ${response.status}`);
  }

  return response.json();
}
```

---

## Managed Identity Authentication

### Configure Managed Identity

```hcl
# infra/modules/function/managed-identity.tf

# Function App System-Assigned Managed Identity
resource "azurerm_linux_function_app" "main" {
  # ... other configuration ...

  identity {
    type = "SystemAssigned"
  }
}

# Grant Function App access to Key Vault
resource "azurerm_key_vault_access_policy" "function_app" {
  key_vault_id = var.key_vault_id
  tenant_id    = data.azurerm_client_config.current.tenant_id
  object_id    = azurerm_linux_function_app.main.identity[0].principal_id

  secret_permissions = [
    "Get",
    "List",
  ]
}

# Grant Function App access to Storage
resource "azurerm_role_assignment" "function_storage" {
  scope                = var.storage_account_id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_linux_function_app.main.identity[0].principal_id
}

# Grant Function App access to Azure OpenAI
resource "azurerm_role_assignment" "function_openai" {
  scope                = var.openai_account_id
  role_definition_name = "Cognitive Services OpenAI User"
  principal_id         = azurerm_linux_function_app.main.identity[0].principal_id
}
```

### Python Function with Managed Identity

Create `func/shared/azure_identity_helper.py`:

```python
"""
PULSE Azure Identity Helper
Managed Identity authentication for Azure services
"""

from functools import lru_cache
from azure.identity import DefaultAzureCredential, ManagedIdentityCredential
from azure.keyvault.secrets import SecretClient
from azure.storage.blob import BlobServiceClient
from openai import AzureOpenAI
import os
import logging

logger = logging.getLogger(__name__)

# Environment detection
def is_local_development() -> bool:
    """Check if running locally."""
    return os.environ.get("AZURE_FUNCTIONS_ENVIRONMENT") == "Development"


@lru_cache(maxsize=1)
def get_credential():
    """Get Azure credential based on environment."""
    if is_local_development():
        # Use DefaultAzureCredential for local dev
        # This will use Azure CLI, VS Code, or other local credentials
        return DefaultAzureCredential()
    else:
        # Use Managed Identity in Azure
        return ManagedIdentityCredential()


@lru_cache(maxsize=1)
def get_keyvault_client() -> SecretClient:
    """Get Key Vault client."""
    vault_url = os.environ["AZURE_KEY_VAULT_URL"]
    credential = get_credential()
    return SecretClient(vault_url=vault_url, credential=credential)


@lru_cache(maxsize=1)
def get_blob_client() -> BlobServiceClient:
    """Get Blob Storage client."""
    account_url = os.environ["AZURE_STORAGE_ACCOUNT_URL"]
    credential = get_credential()
    return BlobServiceClient(account_url=account_url, credential=credential)


@lru_cache(maxsize=1)
def get_openai_client() -> AzureOpenAI:
    """Get Azure OpenAI client."""
    endpoint = os.environ["AZURE_OPENAI_ENDPOINT"]
    credential = get_credential()

    # Get token for Azure OpenAI
    token = credential.get_token("https://cognitiveservices.azure.com/.default")

    return AzureOpenAI(
        azure_endpoint=endpoint,
        api_key=token.token,  # Use token as API key
        api_version="2024-02-01",
    )


def get_secret(secret_name: str) -> str:
    """Get secret from Key Vault."""
    client = get_keyvault_client()
    secret = client.get_secret(secret_name)
    return secret.value
```

### Service-to-Service Call from Web App

Create `ui/lib/internal-function-client.ts`:

```typescript
/**
 * PULSE Internal Function Client
 * Uses Managed Identity for authentication
 */

import { DefaultAzureCredential } from '@azure/identity';

const FUNCTION_APP_URL = process.env.FUNCTION_APP_INTERNAL_URL;
const FUNCTION_APP_CLIENT_ID = process.env.FUNCTION_APP_CLIENT_ID;

let credential: DefaultAzureCredential | null = null;

function getCredential(): DefaultAzureCredential {
  if (!credential) {
    credential = new DefaultAzureCredential();
  }
  return credential;
}

/**
 * Get access token for Function App
 */
async function getAccessToken(): Promise<string> {
  const cred = getCredential();
  const scope = `api://${FUNCTION_APP_CLIENT_ID}/.default`;

  const tokenResponse = await cred.getToken(scope);
  return tokenResponse.token;
}

/**
 * Call internal Function App endpoint
 */
export async function callInternalFunction<T>(
  endpoint: string,
  options: {
    method?: 'GET' | 'POST' | 'PUT' | 'DELETE';
    body?: any;
    headers?: Record<string, string>;
  } = {}
): Promise<T> {
  const { method = 'POST', body, headers = {} } = options;

  const token = await getAccessToken();

  const response = await fetch(`${FUNCTION_APP_URL}/api/${endpoint}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
      ...headers,
    },
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Function call failed: ${response.status} - ${error}`);
  }

  return response.json();
}
```

---

## Function Key Authentication

### Configure Function Keys

```hcl
# infra/modules/function/keys.tf

# Function-level keys (for specific functions)
resource "azurerm_function_app_function" "process_document" {
  name            = "process-document"
  function_app_id = azurerm_linux_function_app.main.id
  language        = "Python"

  config_json = jsonencode({
    bindings = [
      {
        type      = "httpTrigger"
        direction = "in"
        name      = "req"
        methods   = ["post"]
        authLevel = "function"  # Requires function key
      },
      {
        type      = "http"
        direction = "out"
        name      = "$return"
      }
    ]
  })
}

# Store function key in Key Vault
resource "azurerm_key_vault_secret" "function_key" {
  name         = "func-process-document-key"
  value        = azurerm_linux_function_app.main.function_keys["process-document"]
  key_vault_id = var.key_vault_id
}
```

### Python Function with Key Authentication

```python
# func/process_document/__init__.py

import azure.functions as func
import logging

def main(req: func.HttpRequest) -> func.HttpResponse:
    """
    HTTP trigger function with function key authentication.
    The authLevel in function.json handles key validation automatically.
    """
    logging.info("Processing document request")

    try:
        # Get request body
        body = req.get_json()
        document_id = body.get("documentId")

        if not document_id:
            return func.HttpResponse(
                '{"error": "documentId is required"}',
                status_code=400,
                mimetype="application/json"
            )

        # Process document...
        result = {"status": "processed", "documentId": document_id}

        return func.HttpResponse(
            json.dumps(result),
            status_code=200,
            mimetype="application/json"
        )

    except Exception as e:
        logging.error(f"Error processing document: {e}")
        return func.HttpResponse(
            f'{{"error": "{str(e)}"}}',
            status_code=500,
            mimetype="application/json"
        )
```

### Calling with Function Key

```typescript
// ui/lib/function-key-client.ts

const FUNCTION_KEY = process.env.FUNCTION_PROCESS_DOCUMENT_KEY;

export async function processDocument(documentId: string): Promise<any> {
  const response = await fetch(
    `${FUNCTION_APP_URL}/api/process-document?code=${FUNCTION_KEY}`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ documentId }),
    }
  );

  if (!response.ok) {
    throw new Error(`Function call failed: ${response.status}`);
  }

  return response.json();
}
```

---

## Custom JWT Validation

### Python JWT Validator

Create `func/shared/jwt_validator.py`:

```python
"""
PULSE JWT Validator
Custom JWT validation for Function Apps
"""

import jwt
from jwt import PyJWKClient
from functools import lru_cache
import os
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Azure AD configuration
TENANT_ID = os.environ.get("AZURE_AD_TENANT_ID")
CLIENT_ID = os.environ.get("AZURE_AD_CLIENT_ID")
ISSUER = f"https://login.microsoftonline.com/{TENANT_ID}/v2.0"
JWKS_URL = f"https://login.microsoftonline.com/{TENANT_ID}/discovery/v2.0/keys"


@lru_cache(maxsize=1)
def get_jwk_client() -> PyJWKClient:
    """Get cached JWK client."""
    return PyJWKClient(JWKS_URL, cache_keys=True)


class TokenValidationError(Exception):
    """Exception for token validation failures."""
    pass


def validate_token(token: str) -> Dict[str, Any]:
    """
    Validate JWT token and return claims.

    Args:
        token: JWT token string (without 'Bearer ' prefix)

    Returns:
        Dictionary of token claims

    Raises:
        TokenValidationError: If token is invalid
    """
    if not token:
        raise TokenValidationError("No token provided")

    try:
        # Get signing key
        jwk_client = get_jwk_client()
        signing_key = jwk_client.get_signing_key_from_jwt(token)

        # Decode and validate token
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=CLIENT_ID,
            issuer=ISSUER,
            options={
                "require": ["exp", "iat", "iss", "aud", "sub"],
                "verify_exp": True,
                "verify_iat": True,
                "verify_iss": True,
                "verify_aud": True,
            }
        )

        return claims

    except jwt.ExpiredSignatureError:
        raise TokenValidationError("Token has expired")
    except jwt.InvalidAudienceError:
        raise TokenValidationError("Invalid token audience")
    except jwt.InvalidIssuerError:
        raise TokenValidationError("Invalid token issuer")
    except jwt.InvalidTokenError as e:
        raise TokenValidationError(f"Invalid token: {str(e)}")
    except Exception as e:
        logger.error(f"Token validation error: {e}")
        raise TokenValidationError(f"Token validation failed: {str(e)}")


def extract_token(req) -> Optional[str]:
    """
    Extract JWT token from request.

    Args:
        req: Azure Functions HttpRequest

    Returns:
        Token string or None
    """
    auth_header = req.headers.get("Authorization", "")

    if auth_header.startswith("Bearer "):
        return auth_header[7:]

    # Also check for token in query string (not recommended for production)
    return req.params.get("access_token")


def get_user_id(claims: Dict[str, Any]) -> str:
    """Extract user ID from token claims."""
    return claims.get("oid") or claims.get("sub")


def get_user_email(claims: Dict[str, Any]) -> Optional[str]:
    """Extract user email from token claims."""
    return claims.get("email") or claims.get("preferred_username")


def has_required_role(claims: Dict[str, Any], required_role: str) -> bool:
    """Check if user has required role."""
    roles = claims.get("roles", [])
    return required_role in roles


def has_required_scope(claims: Dict[str, Any], required_scope: str) -> bool:
    """Check if token has required scope."""
    scopes = claims.get("scp", "").split()
    return required_scope in scopes
```

### Authentication Decorator

Create `func/shared/auth_decorator.py`:

```python
"""
PULSE Function Authentication Decorators
"""

import azure.functions as func
from functools import wraps
import json
import logging
from typing import Callable, List, Optional
from .jwt_validator import (
    validate_token,
    extract_token,
    get_user_id,
    has_required_role,
    has_required_scope,
    TokenValidationError,
)

logger = logging.getLogger(__name__)


def require_auth(
    roles: Optional[List[str]] = None,
    scopes: Optional[List[str]] = None,
    allow_anonymous: bool = False,
):
    """
    Decorator to require authentication for a function.

    Args:
        roles: Required roles (user must have at least one)
        scopes: Required scopes (token must have at least one)
        allow_anonymous: Allow unauthenticated access
    """
    def decorator(func_handler: Callable):
        @wraps(func_handler)
        def wrapper(req: func.HttpRequest, *args, **kwargs) -> func.HttpResponse:
            # Extract token
            token = extract_token(req)

            if not token:
                if allow_anonymous:
                    # Add empty user context
                    req.user = None
                    return func_handler(req, *args, **kwargs)
                return create_error_response("Authorization required", 401)

            try:
                # Validate token
                claims = validate_token(token)

                # Check roles
                if roles:
                    has_role = any(has_required_role(claims, role) for role in roles)
                    if not has_role:
                        logger.warning(
                            f"User {get_user_id(claims)} lacks required roles: {roles}"
                        )
                        return create_error_response("Insufficient permissions", 403)

                # Check scopes
                if scopes:
                    has_scope = any(has_required_scope(claims, scope) for scope in scopes)
                    if not has_scope:
                        logger.warning(
                            f"Token lacks required scopes: {scopes}"
                        )
                        return create_error_response("Insufficient scope", 403)

                # Add user context to request
                req.user = {
                    "id": get_user_id(claims),
                    "claims": claims,
                }

                return func_handler(req, *args, **kwargs)

            except TokenValidationError as e:
                logger.warning(f"Token validation failed: {e}")
                return create_error_response(str(e), 401)

        return wrapper
    return decorator


def require_roles(*roles: str):
    """Shorthand for requiring specific roles."""
    return require_auth(roles=list(roles))


def require_scopes(*scopes: str):
    """Shorthand for requiring specific scopes."""
    return require_auth(scopes=list(scopes))


def create_error_response(message: str, status_code: int) -> func.HttpResponse:
    """Create error response."""
    return func.HttpResponse(
        json.dumps({"error": message}),
        status_code=status_code,
        mimetype="application/json",
        headers={
            "WWW-Authenticate": 'Bearer error="invalid_token"' if status_code == 401 else None
        }
    )
```

### Using the Decorator

```python
# func/protected_function/__init__.py

import azure.functions as func
import json
from shared.auth_decorator import require_auth, require_roles


@require_auth()
def main(req: func.HttpRequest) -> func.HttpResponse:
    """Protected function that requires any valid token."""
    user = req.user

    return func.HttpResponse(
        json.dumps({
            "message": f"Hello, {user['id']}",
            "claims": user["claims"]
        }),
        mimetype="application/json"
    )


# Or with role requirements
@require_roles("Admin", "Manager")
def admin_function(req: func.HttpRequest) -> func.HttpResponse:
    """Function requiring Admin or Manager role."""
    # ... implementation
    pass
```

---

## Service-to-Service Authentication

### On-Behalf-Of Flow

```python
# func/shared/on_behalf_of.py

"""
PULSE On-Behalf-Of Token Exchange
Exchange user token for downstream service token
"""

import os
import requests
from functools import lru_cache
import logging

logger = logging.getLogger(__name__)

TENANT_ID = os.environ["AZURE_AD_TENANT_ID"]
CLIENT_ID = os.environ["AZURE_AD_CLIENT_ID"]
CLIENT_SECRET = os.environ["AZURE_AD_CLIENT_SECRET"]
TOKEN_URL = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"


def exchange_token(user_token: str, target_scope: str) -> str:
    """
    Exchange user token for a token scoped to a downstream service.

    Args:
        user_token: The user's access token
        target_scope: Scope for the target service (e.g., 'api://downstream-api/.default')

    Returns:
        Access token for the target service
    """
    data = {
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "assertion": user_token,
        "scope": target_scope,
        "requested_token_use": "on_behalf_of",
    }

    response = requests.post(TOKEN_URL, data=data)

    if response.status_code != 200:
        logger.error(f"Token exchange failed: {response.text}")
        raise Exception(f"Token exchange failed: {response.status_code}")

    return response.json()["access_token"]


async def call_downstream_service(
    user_token: str,
    service_url: str,
    target_scope: str,
    method: str = "GET",
    payload: dict = None,
) -> dict:
    """
    Call a downstream service on behalf of the user.

    Args:
        user_token: The user's access token
        service_url: URL of the downstream service
        target_scope: Scope for the target service
        method: HTTP method
        payload: Request payload for POST/PUT

    Returns:
        Response from downstream service
    """
    # Exchange token
    downstream_token = exchange_token(user_token, target_scope)

    # Call downstream service
    headers = {
        "Authorization": f"Bearer {downstream_token}",
        "Content-Type": "application/json",
    }

    if method == "GET":
        response = requests.get(service_url, headers=headers)
    else:
        response = requests.request(
            method,
            service_url,
            headers=headers,
            json=payload
        )

    response.raise_for_status()
    return response.json()
```

---

## Authorization Controls

### Role-Based Access Control

Create `func/shared/authorization.py`:

```python
"""
PULSE Authorization
Role and permission checks
"""

from enum import Enum
from typing import List, Dict, Any, Set


class Role(Enum):
    """Available roles in PULSE."""
    USER = "User"
    POWER_USER = "PowerUser"
    ADMIN = "Admin"
    SUPER_ADMIN = "SuperAdmin"


class Permission(Enum):
    """Available permissions."""
    READ_CHAT = "read:chat"
    WRITE_CHAT = "write:chat"
    READ_DOCUMENTS = "read:documents"
    WRITE_DOCUMENTS = "write:documents"
    DELETE_DOCUMENTS = "delete:documents"
    MANAGE_USERS = "manage:users"
    VIEW_ANALYTICS = "view:analytics"
    ADMIN_SETTINGS = "admin:settings"


# Role to permission mapping
ROLE_PERMISSIONS: Dict[Role, Set[Permission]] = {
    Role.USER: {
        Permission.READ_CHAT,
        Permission.WRITE_CHAT,
        Permission.READ_DOCUMENTS,
    },
    Role.POWER_USER: {
        Permission.READ_CHAT,
        Permission.WRITE_CHAT,
        Permission.READ_DOCUMENTS,
        Permission.WRITE_DOCUMENTS,
        Permission.VIEW_ANALYTICS,
    },
    Role.ADMIN: {
        Permission.READ_CHAT,
        Permission.WRITE_CHAT,
        Permission.READ_DOCUMENTS,
        Permission.WRITE_DOCUMENTS,
        Permission.DELETE_DOCUMENTS,
        Permission.MANAGE_USERS,
        Permission.VIEW_ANALYTICS,
    },
    Role.SUPER_ADMIN: set(Permission),  # All permissions
}


def get_user_roles(claims: Dict[str, Any]) -> List[Role]:
    """Extract roles from token claims."""
    role_strings = claims.get("roles", [])
    roles = []

    for role_str in role_strings:
        try:
            roles.append(Role(role_str))
        except ValueError:
            pass  # Ignore unknown roles

    return roles if roles else [Role.USER]  # Default to User


def get_user_permissions(claims: Dict[str, Any]) -> Set[Permission]:
    """Get all permissions for a user based on their roles."""
    roles = get_user_roles(claims)
    permissions: Set[Permission] = set()

    for role in roles:
        permissions.update(ROLE_PERMISSIONS.get(role, set()))

    return permissions


def has_permission(claims: Dict[str, Any], permission: Permission) -> bool:
    """Check if user has a specific permission."""
    permissions = get_user_permissions(claims)
    return permission in permissions


def require_permission(*permissions: Permission):
    """
    Decorator to require specific permissions.

    Usage:
        @require_permission(Permission.WRITE_DOCUMENTS)
        def upload_document(req):
            ...
    """
    from functools import wraps
    import azure.functions as func
    import json

    def decorator(func_handler):
        @wraps(func_handler)
        def wrapper(req: func.HttpRequest, *args, **kwargs):
            user = getattr(req, "user", None)

            if not user:
                return func.HttpResponse(
                    '{"error": "Authentication required"}',
                    status_code=401,
                    mimetype="application/json"
                )

            user_permissions = get_user_permissions(user["claims"])

            # Check if user has any of the required permissions
            if not any(p in user_permissions for p in permissions):
                return func.HttpResponse(
                    '{"error": "Insufficient permissions"}',
                    status_code=403,
                    mimetype="application/json"
                )

            return func_handler(req, *args, **kwargs)

        return wrapper
    return decorator
```

---

## Terraform Implementation

### Complete Function Auth Module

Create `infra/modules/function/main.tf`:

```hcl
# Azure Function App with Complete Authentication

terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
    azuread = {
      source  = "hashicorp/azuread"
      version = "~> 2.0"
    }
  }
}

variable "resource_group_name" { type = string }
variable "location" { type = string }
variable "environment" { type = string }
variable "azure_ad_tenant_id" { type = string }
variable "storage_account_name" { type = string }
variable "storage_account_key" { type = string }
variable "key_vault_id" { type = string }
variable "allowed_origins" { type = list(string) }
variable "tags" { type = map(string) }

# App Service Plan
resource "azurerm_service_plan" "main" {
  name                = "asp-func-pulse-${var.environment}"
  resource_group_name = var.resource_group_name
  location            = var.location
  os_type             = "Linux"
  sku_name            = "P1v3"

  tags = var.tags
}

# App Registration for Function App
resource "azuread_application" "func" {
  display_name = "PULSE-Function-${var.environment}"

  api {
    oauth2_permission_scope {
      admin_consent_description  = "Access PULSE Functions"
      admin_consent_display_name = "Access PULSE Functions"
      enabled                    = true
      id                         = random_uuid.func_scope.result
      type                       = "User"
      value                      = "user_impersonation"
    }
  }

  app_role {
    allowed_member_types = ["User"]
    description          = "Admin access to PULSE functions"
    display_name         = "Admin"
    enabled              = true
    id                   = random_uuid.admin_role.result
    value                = "Admin"
  }

  app_role {
    allowed_member_types = ["User"]
    description          = "User access to PULSE functions"
    display_name         = "User"
    enabled              = true
    id                   = random_uuid.user_role.result
    value                = "User"
  }
}

resource "azuread_service_principal" "func" {
  client_id = azuread_application.func.client_id
}

resource "azuread_application_password" "func" {
  application_id = azuread_application.func.id
  display_name   = "Function App Secret"
  end_date       = "2099-01-01T00:00:00Z"
}

resource "random_uuid" "func_scope" {}
resource "random_uuid" "admin_role" {}
resource "random_uuid" "user_role" {}

# Function App
resource "azurerm_linux_function_app" "main" {
  name                = "func-pulse-${var.environment}"
  resource_group_name = var.resource_group_name
  location            = var.location
  service_plan_id     = azurerm_service_plan.main.id

  storage_account_name       = var.storage_account_name
  storage_account_access_key = var.storage_account_key

  https_only = true

  site_config {
    always_on                         = true
    application_insights_connection_string = var.app_insights_connection_string

    application_stack {
      python_version = "3.11"
    }

    cors {
      allowed_origins     = var.allowed_origins
      support_credentials = true
    }
  }

  auth_settings_v2 {
    auth_enabled             = true
    require_authentication   = true
    unauthenticated_action   = "Return401"
    default_provider         = "azureactivedirectory"
    require_https            = true

    active_directory_v2 {
      client_id                  = azuread_application.func.client_id
      tenant_auth_endpoint       = "https://login.microsoftonline.com/${var.azure_ad_tenant_id}/v2.0"
      allowed_audiences          = [
        azuread_application.func.client_id,
        "api://${azuread_application.func.client_id}"
      ]
      client_secret_setting_name = "AZURE_AD_CLIENT_SECRET"
    }

    login {
      token_store_enabled = true
    }
  }

  app_settings = {
    FUNCTIONS_WORKER_RUNTIME    = "python"
    AZURE_AD_CLIENT_ID          = azuread_application.func.client_id
    AZURE_AD_TENANT_ID          = var.azure_ad_tenant_id
    AZURE_AD_CLIENT_SECRET      = "@Microsoft.KeyVault(SecretUri=${azurerm_key_vault_secret.func_secret.id})"
    AZURE_KEY_VAULT_URL         = data.azurerm_key_vault.main.vault_uri
  }

  identity {
    type = "SystemAssigned"
  }

  tags = var.tags
}

# Store client secret in Key Vault
resource "azurerm_key_vault_secret" "func_secret" {
  name         = "func-client-secret"
  value        = azuread_application_password.func.value
  key_vault_id = var.key_vault_id
}

# Grant Function App access to Key Vault
resource "azurerm_key_vault_access_policy" "func" {
  key_vault_id = var.key_vault_id
  tenant_id    = data.azurerm_client_config.current.tenant_id
  object_id    = azurerm_linux_function_app.main.identity[0].principal_id

  secret_permissions = ["Get", "List"]
}

# Outputs
output "function_app_url" {
  value = "https://${azurerm_linux_function_app.main.default_hostname}"
}

output "client_id" {
  value = azuread_application.func.client_id
}

output "principal_id" {
  value = azurerm_linux_function_app.main.identity[0].principal_id
}
```

---

## Testing and Validation

### Authentication Test Script

Create `scripts/test-func-auth.sh`:

```bash
#!/bin/bash
# PULSE Function App Authentication Tests

set -e

FUNCTION_URL="${1:-https://func-pulse-prod.azurewebsites.net}"
echo "Testing Function App auth at: $FUNCTION_URL"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

test_auth() {
    local name="$1"
    local endpoint="$2"
    local token="$3"
    local expected="$4"

    echo -n "Testing: $name... "

    if [ -n "$token" ]; then
        status=$(curl -s -o /dev/null -w "%{http_code}" \
            -H "Authorization: Bearer $token" \
            "$FUNCTION_URL$endpoint")
    else
        status=$(curl -s -o /dev/null -w "%{http_code}" \
            "$FUNCTION_URL$endpoint")
    fi

    if [ "$status" == "$expected" ]; then
        echo -e "${GREEN}PASS${NC} (got $status)"
    else
        echo -e "${RED}FAIL${NC} (expected $expected, got $status)"
    fi
}

echo "=== Unauthenticated Tests ==="
test_auth "No auth header" "/api/protected" "" "401"
test_auth "Invalid token" "/api/protected" "invalid-token" "401"
test_auth "Expired token" "/api/protected" "expired.token.here" "401"

echo ""
echo "=== Authenticated Tests ==="
# Get a valid token (you'd need to implement this)
# TOKEN=$(az account get-access-token --resource api://your-client-id --query accessToken -o tsv)
# test_auth "Valid token" "/api/protected" "$TOKEN" "200"

echo ""
echo "=== Function Key Tests ==="
# test_auth "With function key" "/api/process-document?code=your-key" "" "200"

echo ""
echo "=== Auth Tests Complete ==="
```

### Python Unit Tests

Create `func/tests/test_auth.py`:

```python
"""
PULSE Function Authentication Tests
"""

import pytest
from unittest.mock import Mock, patch
from shared.jwt_validator import validate_token, TokenValidationError
from shared.auth_decorator import require_auth


class TestJwtValidator:
    def test_missing_token(self):
        with pytest.raises(TokenValidationError) as exc:
            validate_token("")
        assert "No token provided" in str(exc.value)

    def test_invalid_token_format(self):
        with pytest.raises(TokenValidationError) as exc:
            validate_token("not.a.valid.token")
        assert "Invalid token" in str(exc.value) or "Token validation failed" in str(exc.value)

    @patch('shared.jwt_validator.get_jwk_client')
    def test_expired_token(self, mock_jwk_client):
        # Test with an expired token (mock the response)
        import jwt
        from datetime import datetime, timedelta

        mock_key = Mock()
        mock_key.key = "test-key"
        mock_jwk_client.return_value.get_signing_key_from_jwt.return_value = mock_key

        with pytest.raises(TokenValidationError) as exc:
            validate_token("expired.jwt.token")
        # Should raise some form of token error


class TestAuthDecorator:
    def test_no_token_returns_401(self):
        @require_auth()
        def protected_function(req):
            return Mock(status_code=200)

        req = Mock()
        req.headers = {}
        req.params = {}

        response = protected_function(req)
        assert response.status_code == 401

    def test_invalid_token_returns_401(self):
        @require_auth()
        def protected_function(req):
            return Mock(status_code=200)

        req = Mock()
        req.headers = {"Authorization": "Bearer invalid-token"}
        req.params = {}

        response = protected_function(req)
        assert response.status_code == 401
```

---

## Migration Checklist

### Phase 1: Azure AD Setup

- [ ] Create App Registration for Function App
- [ ] Configure API permissions and scopes
- [ ] Define app roles (Admin, User, etc.)
- [ ] Generate client secret and store in Key Vault

### Phase 2: Function App Configuration

- [ ] Enable built-in authentication
- [ ] Configure Azure AD provider
- [ ] Enable Managed Identity
- [ ] Set up Key Vault access

### Phase 3: Code Implementation

- [ ] Create JWT validator
- [ ] Implement auth decorator
- [ ] Add authorization helpers
- [ ] Update existing functions with auth

### Phase 4: Service Integration

- [ ] Configure Web App to call Function App
- [ ] Implement token acquisition
- [ ] Set up Managed Identity for service-to-service
- [ ] Test On-Behalf-Of flow

### Phase 5: Testing

- [ ] Test unauthenticated access (should fail)
- [ ] Test with valid tokens
- [ ] Test role-based access
- [ ] Test service-to-service calls

---

## Best Practices Summary

1. **Use Azure AD**: Prefer built-in Azure AD auth
2. **Managed Identity**: For service-to-service calls
3. **Function Keys**: Only for simple scenarios
4. **JWT Validation**: Validate on every request
5. **Role-Based**: Implement proper authorization
6. **Audit**: Log all authentication events

---

## Related Documents

- [securedbydesign.md](securedbydesign.md) - Overall security assessment
- [managedid.md](managedid.md) - Managed Identity guide
- [secretsmanage.md](secretsmanage.md) - Secrets management
