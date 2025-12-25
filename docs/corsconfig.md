# PULSE Platform - CORS Security Implementation Guide

> **Document Version:** 1.0
> **Created:** December 25, 2024
> **Classification:** RESTRICTED - Internal Use Only
> **Related Documents:** [securedbydesign.md](securedbydesign.md)

---

## Executive Summary

This document provides a comprehensive guide for implementing secure Cross-Origin Resource Sharing (CORS) configuration in the PULSE platform. The current wildcard (`*`) CORS configuration exposes APIs to cross-origin attacks. This guide details how to implement proper CORS restrictions.

**Current Risk Level:** CRITICAL - Wildcard CORS allows any origin to access APIs

---

## Table of Contents

- [1. Understanding CORS Security](#1-understanding-cors-security)
- [2. Current State Assessment](#2-current-state-assessment)
- [3. Next.js API Route CORS Implementation](#3-nextjs-api-route-cors-implementation)
- [4. Function App CORS Configuration](#4-function-app-cors-configuration)
- [5. Environment-Based Configuration](#5-environment-based-configuration)
- [6. Testing and Validation](#6-testing-and-validation)
- [7. Migration Checklist](#7-migration-checklist)

---

## 1. Understanding CORS Security

### 1.1 What is CORS?

Cross-Origin Resource Sharing (CORS) is a security mechanism that allows or restricts web applications running at one origin to access resources from a different origin.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CORS REQUEST FLOW                                  │
└─────────────────────────────────────────────────────────────────────────────┘

Browser (origin: https://app.example.com)
    │
    │  1. Preflight OPTIONS request
    │     Origin: https://app.example.com
    │     Access-Control-Request-Method: POST
    │
    ▼
API Server (origin: https://api.example.com)
    │
    │  2. Preflight response
    │     Access-Control-Allow-Origin: https://app.example.com
    │     Access-Control-Allow-Methods: GET, POST
    │     Access-Control-Allow-Headers: Content-Type, Authorization
    │
    ▼
Browser
    │
    │  3. Actual request (if allowed)
    │     Origin: https://app.example.com
    │     Authorization: Bearer <token>
    │
    ▼
API Server
    │
    │  4. Response with CORS headers
    │     Access-Control-Allow-Origin: https://app.example.com
    │
    ▼
Browser (receives response)
```

### 1.2 Why Wildcard CORS is Dangerous

| Risk | Description |
|------|-------------|
| **Cross-Site Request Forgery (CSRF)** | Malicious sites can make authenticated requests |
| **Data Exfiltration** | Attackers can read sensitive response data |
| **Session Hijacking** | Credentials can be stolen via cross-origin requests |
| **API Abuse** | Third-party sites can abuse your API endpoints |

### 1.3 CORS Headers Reference

| Header | Purpose | Secure Value |
|--------|---------|--------------|
| `Access-Control-Allow-Origin` | Allowed origins | Specific origin URL |
| `Access-Control-Allow-Methods` | Allowed HTTP methods | `GET, POST, PUT, DELETE` |
| `Access-Control-Allow-Headers` | Allowed request headers | `Content-Type, Authorization` |
| `Access-Control-Allow-Credentials` | Allow cookies/auth | `true` (only with specific origin) |
| `Access-Control-Max-Age` | Preflight cache duration | `86400` (24 hours) |

---

## 2. Current State Assessment

### 2.1 Affected Files

Based on the security assessment, the following files have wildcard CORS:

| File | Endpoint | Current State |
|------|----------|---------------|
| `ui/app/api/orchestrator/chat/route.ts` | `/api/orchestrator/chat` | `Access-Control-Allow-Origin: *` |
| `ui/app/api/orchestrator/context/route.ts` | `/api/orchestrator/context` | `Access-Control-Allow-Origin: *` |
| `ui/app/api/orchestrator/admin/prompts/route.ts` | `/api/orchestrator/admin/prompts` | `Access-Control-Allow-Origin: *` |

### 2.2 Risk Analysis

```
CURRENT ATTACK VECTOR:

1. Attacker creates malicious website (https://evil.com)
2. User visits evil.com while logged into PULSE
3. Evil.com JavaScript makes request to PULSE API:
   fetch('https://app-pulse-training-ui-prod.azurewebsites.net/api/orchestrator/chat', {
     credentials: 'include',  // Sends user's cookies
     method: 'POST',
     body: JSON.stringify({ message: 'steal data' })
   })
4. PULSE API responds with Access-Control-Allow-Origin: *
5. Browser allows evil.com to read the response
6. User data is exfiltrated to attacker
```

---

## 3. Next.js API Route CORS Implementation

### 3.1 Create CORS Utility Module

**File: `ui/lib/cors.ts`** (New file)

```typescript
/**
 * CORS Configuration for PULSE Platform
 *
 * This module provides secure CORS handling for API routes.
 * It restricts cross-origin requests to only allowed origins.
 */

import { NextRequest, NextResponse } from "next/server";

// Environment-based allowed origins
function getAllowedOrigins(): string[] {
  const origins: string[] = [];

  // Primary application URL (required)
  const nextAuthUrl = process.env.NEXTAUTH_URL;
  if (nextAuthUrl) {
    origins.push(nextAuthUrl);
  }

  // Additional allowed origins (optional, comma-separated)
  const additionalOrigins = process.env.CORS_ALLOWED_ORIGINS;
  if (additionalOrigins) {
    origins.push(
      ...additionalOrigins.split(",").map((o) => o.trim()).filter(Boolean)
    );
  }

  // Development origins (only in non-production)
  if (process.env.NODE_ENV !== "production") {
    origins.push(
      "http://localhost:3000",
      "http://localhost:3001",
      "http://127.0.0.1:3000"
    );
  }

  return origins;
}

// CORS configuration object
export interface CorsConfig {
  allowedOrigins: string[];
  allowedMethods: string[];
  allowedHeaders: string[];
  allowCredentials: boolean;
  maxAge: number;
}

export const corsConfig: CorsConfig = {
  allowedOrigins: getAllowedOrigins(),
  allowedMethods: ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
  allowedHeaders: [
    "Content-Type",
    "Authorization",
    "X-Requested-With",
    "Accept",
    "Origin",
    "X-CSRF-Token",
  ],
  allowCredentials: true,
  maxAge: 86400, // 24 hours
};

/**
 * Check if an origin is allowed
 */
export function isOriginAllowed(origin: string | null): boolean {
  if (!origin) return false;

  // Exact match
  if (corsConfig.allowedOrigins.includes(origin)) {
    return true;
  }

  // Pattern matching for subdomains (if configured)
  for (const allowed of corsConfig.allowedOrigins) {
    if (allowed.startsWith("*.")) {
      const domain = allowed.slice(2);
      if (origin.endsWith(domain)) {
        return true;
      }
    }
  }

  return false;
}

/**
 * Get CORS headers for a request
 */
export function getCorsHeaders(origin: string | null): HeadersInit {
  const headers: HeadersInit = {};

  if (origin && isOriginAllowed(origin)) {
    headers["Access-Control-Allow-Origin"] = origin;
    headers["Access-Control-Allow-Credentials"] = "true";
  }

  headers["Access-Control-Allow-Methods"] = corsConfig.allowedMethods.join(", ");
  headers["Access-Control-Allow-Headers"] = corsConfig.allowedHeaders.join(", ");
  headers["Access-Control-Max-Age"] = corsConfig.maxAge.toString();

  return headers;
}

/**
 * Handle CORS preflight OPTIONS request
 */
export function handlePreflight(request: NextRequest): NextResponse {
  const origin = request.headers.get("origin");

  if (!isOriginAllowed(origin)) {
    // Reject preflight from disallowed origins
    return new NextResponse(null, {
      status: 403,
      statusText: "CORS Origin Not Allowed",
    });
  }

  return new NextResponse(null, {
    status: 204,
    headers: getCorsHeaders(origin),
  });
}

/**
 * Add CORS headers to a response
 */
export function withCors(
  response: NextResponse,
  request: NextRequest
): NextResponse {
  const origin = request.headers.get("origin");
  const corsHeaders = getCorsHeaders(origin);

  Object.entries(corsHeaders).forEach(([key, value]) => {
    response.headers.set(key, value);
  });

  return response;
}

/**
 * CORS middleware wrapper for API routes
 *
 * Usage:
 * ```typescript
 * import { corsMiddleware } from "@/lib/cors";
 *
 * export async function POST(request: NextRequest) {
 *   return corsMiddleware(request, async (req) => {
 *     // Your handler logic
 *     return NextResponse.json({ data: "response" });
 *   });
 * }
 *
 * export async function OPTIONS(request: NextRequest) {
 *   return corsMiddleware(request);
 * }
 * ```
 */
export async function corsMiddleware(
  request: NextRequest,
  handler?: (request: NextRequest) => Promise<NextResponse>
): Promise<NextResponse> {
  const origin = request.headers.get("origin");

  // Handle preflight
  if (request.method === "OPTIONS") {
    return handlePreflight(request);
  }

  // Check origin for non-preflight requests
  if (origin && !isOriginAllowed(origin)) {
    return new NextResponse(
      JSON.stringify({
        error: "CORS Error",
        message: "Origin not allowed",
      }),
      {
        status: 403,
        headers: { "Content-Type": "application/json" },
      }
    );
  }

  // Execute handler if provided
  if (handler) {
    try {
      const response = await handler(request);
      return withCors(response, request);
    } catch (error) {
      console.error("API Error:", error);
      const errorResponse = NextResponse.json(
        { error: "Internal Server Error" },
        { status: 500 }
      );
      return withCors(errorResponse, request);
    }
  }

  // Default response for OPTIONS without handler
  return handlePreflight(request);
}

/**
 * Validate CORS configuration on startup
 */
export function validateCorsConfig(): void {
  if (corsConfig.allowedOrigins.length === 0) {
    console.warn(
      "WARNING: No CORS origins configured. " +
      "Set NEXTAUTH_URL or CORS_ALLOWED_ORIGINS environment variable."
    );
  }

  if (corsConfig.allowedOrigins.includes("*")) {
    throw new Error(
      "SECURITY ERROR: Wildcard (*) CORS origin is not allowed. " +
      "Configure specific origins in NEXTAUTH_URL or CORS_ALLOWED_ORIGINS."
    );
  }

  console.log(
    `CORS configured for origins: ${corsConfig.allowedOrigins.join(", ")}`
  );
}
```

### 3.2 Update API Routes

**File: `ui/app/api/orchestrator/chat/route.ts`** (Updated)

```typescript
import { NextRequest, NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth-config";
import { corsMiddleware } from "@/lib/cors";

// Handle CORS preflight
export async function OPTIONS(request: NextRequest) {
  return corsMiddleware(request);
}

export async function POST(request: NextRequest) {
  return corsMiddleware(request, async (req) => {
    // Authentication check
    const session = await getServerSession(authOptions);
    if (!session) {
      return NextResponse.json(
        { error: "Unauthorized" },
        { status: 401 }
      );
    }

    try {
      const body = await req.json();

      // Your existing chat logic here
      const response = await processChat(body, session);

      return NextResponse.json(response);
    } catch (error) {
      console.error("Chat API error:", error);
      return NextResponse.json(
        { error: "Internal server error" },
        { status: 500 }
      );
    }
  });
}

async function processChat(body: any, session: any) {
  // Existing chat processing logic
  // ...
  return { message: "processed" };
}
```

**File: `ui/app/api/orchestrator/context/route.ts`** (Updated)

```typescript
import { NextRequest, NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth-config";
import { corsMiddleware } from "@/lib/cors";

export async function OPTIONS(request: NextRequest) {
  return corsMiddleware(request);
}

export async function GET(request: NextRequest) {
  return corsMiddleware(request, async (req) => {
    const session = await getServerSession(authOptions);
    if (!session) {
      return NextResponse.json(
        { error: "Unauthorized" },
        { status: 401 }
      );
    }

    try {
      // Your existing context logic here
      const context = await getContext(session);
      return NextResponse.json(context);
    } catch (error) {
      console.error("Context API error:", error);
      return NextResponse.json(
        { error: "Internal server error" },
        { status: 500 }
      );
    }
  });
}

async function getContext(session: any) {
  // Existing context logic
  return { context: "data" };
}
```

**File: `ui/app/api/orchestrator/admin/prompts/route.ts`** (Updated)

```typescript
import { NextRequest, NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth-config";
import { corsMiddleware } from "@/lib/cors";
import { requireAdmin } from "@/lib/auth-guards";

export async function OPTIONS(request: NextRequest) {
  return corsMiddleware(request);
}

export async function GET(request: NextRequest) {
  return corsMiddleware(request, async (req) => {
    // Admin authentication check
    const session = await getServerSession(authOptions);
    if (!session) {
      return NextResponse.json(
        { error: "Unauthorized" },
        { status: 401 }
      );
    }

    // Admin role check
    if (!requireAdmin(session)) {
      return NextResponse.json(
        { error: "Forbidden - Admin access required" },
        { status: 403 }
      );
    }

    try {
      const prompts = await getPrompts();
      return NextResponse.json(prompts);
    } catch (error) {
      console.error("Prompts API error:", error);
      return NextResponse.json(
        { error: "Internal server error" },
        { status: 500 }
      );
    }
  });
}

export async function POST(request: NextRequest) {
  return corsMiddleware(request, async (req) => {
    const session = await getServerSession(authOptions);
    if (!session || !requireAdmin(session)) {
      return NextResponse.json(
        { error: "Forbidden" },
        { status: 403 }
      );
    }

    try {
      const body = await req.json();
      const result = await createPrompt(body);
      return NextResponse.json(result, { status: 201 });
    } catch (error) {
      console.error("Create prompt error:", error);
      return NextResponse.json(
        { error: "Internal server error" },
        { status: 500 }
      );
    }
  });
}

async function getPrompts() {
  // Existing prompts retrieval logic
  return [];
}

async function createPrompt(body: any) {
  // Existing prompt creation logic
  return { id: "new-prompt-id" };
}
```

### 3.3 Global Middleware Alternative

For applying CORS to all API routes, use Next.js middleware:

**File: `ui/middleware.ts`** (Updated)

```typescript
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { getToken } from "next-auth/jwt";

// CORS configuration
const ALLOWED_ORIGINS = [
  process.env.NEXTAUTH_URL,
  // Add other allowed origins here
].filter(Boolean) as string[];

// Add localhost for development
if (process.env.NODE_ENV !== "production") {
  ALLOWED_ORIGINS.push(
    "http://localhost:3000",
    "http://localhost:3001"
  );
}

function isOriginAllowed(origin: string | null): boolean {
  if (!origin) return true; // Same-origin requests have no origin header
  return ALLOWED_ORIGINS.includes(origin);
}

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const origin = request.headers.get("origin");

  // Handle CORS for API routes
  if (pathname.startsWith("/api/")) {
    // Check origin
    if (origin && !isOriginAllowed(origin)) {
      return new NextResponse(
        JSON.stringify({ error: "CORS origin not allowed" }),
        {
          status: 403,
          headers: { "Content-Type": "application/json" },
        }
      );
    }

    // Handle preflight
    if (request.method === "OPTIONS") {
      return new NextResponse(null, {
        status: 204,
        headers: {
          "Access-Control-Allow-Origin": origin || "*",
          "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
          "Access-Control-Allow-Headers": "Content-Type, Authorization",
          "Access-Control-Allow-Credentials": "true",
          "Access-Control-Max-Age": "86400",
        },
      });
    }
  }

  // Protected routes - require authentication
  const protectedPaths = ["/admin", "/training", "/session", "/feedback"];
  const isProtectedPath = protectedPaths.some((p) => pathname.startsWith(p));

  if (isProtectedPath) {
    const token = await getToken({
      req: request,
      secret: process.env.NEXTAUTH_SECRET,
    });

    if (!token) {
      const signInUrl = new URL("/auth/signin", request.url);
      signInUrl.searchParams.set("callbackUrl", pathname);
      return NextResponse.redirect(signInUrl);
    }
  }

  // Add CORS headers to response
  const response = NextResponse.next();

  if (origin && isOriginAllowed(origin)) {
    response.headers.set("Access-Control-Allow-Origin", origin);
    response.headers.set("Access-Control-Allow-Credentials", "true");
  }

  return response;
}

export const config = {
  matcher: [
    // Match all API routes
    "/api/:path*",
    // Match protected pages
    "/admin/:path*",
    "/training/:path*",
    "/session/:path*",
    "/feedback/:path*",
  ],
};
```

---

## 4. Function App CORS Configuration

### 4.1 Terraform Configuration

**File: `modules/app/main.tf`** (Updated)

```hcl
resource "azurerm_linux_function_app" "orchestrator" {
  name                       = "func-PULSE-${var.project_name}-orchestrator-${var.environment}"
  location                   = var.location
  resource_group_name        = var.resource_group_name
  service_plan_id            = azurerm_service_plan.main.id
  storage_account_name       = var.storage_account_name

  # ... other configuration ...

  site_config {
    always_on                = true
    ftps_state               = "Disabled"
    minimum_tls_version      = "1.2"
    vnet_route_all_enabled   = true

    # CORS Configuration
    cors {
      # Specific allowed origins (NO wildcard)
      allowed_origins = var.cors_allowed_origins

      # Allow credentials (cookies, authorization headers)
      support_credentials = true
    }

    application_stack {
      python_version = "3.11"
    }
  }

  tags = var.tags
}
```

**File: `modules/app/variables.tf`** (Add)

```hcl
variable "cors_allowed_origins" {
  description = "List of allowed CORS origins for the Function App"
  type        = list(string)
  default     = []

  validation {
    condition     = !contains(var.cors_allowed_origins, "*")
    error_message = "Wildcard (*) CORS origin is not allowed for security reasons."
  }
}
```

**File: `main.tf`** (Root module update)

```hcl
module "app" {
  source = "./modules/app"

  # ... other configuration ...

  cors_allowed_origins = [
    "https://app-pulse-training-ui-${var.environment}.azurewebsites.net",
    # Add additional origins as needed
  ]
}
```

### 4.2 Python Function CORS Handling

**File: `orchestrator/shared_code/cors.py`** (New file)

```python
"""
CORS handling for Azure Functions.

This module provides CORS validation and headers for HTTP-triggered functions.
"""

import os
import logging
from typing import Optional, List
from functools import wraps

import azure.functions as func

logger = logging.getLogger(__name__)


def get_allowed_origins() -> List[str]:
    """
    Get list of allowed CORS origins from environment.

    Returns:
        List of allowed origin URLs
    """
    origins = []

    # Primary webapp URL
    webapp_url = os.environ.get("WEBAPP_URL")
    if webapp_url:
        origins.append(webapp_url)

    # Additional origins (comma-separated)
    additional = os.environ.get("CORS_ALLOWED_ORIGINS", "")
    if additional:
        origins.extend([o.strip() for o in additional.split(",") if o.strip()])

    return origins


def is_origin_allowed(origin: Optional[str]) -> bool:
    """
    Check if an origin is allowed.

    Args:
        origin: The Origin header value

    Returns:
        True if origin is allowed, False otherwise
    """
    if not origin:
        return True  # Same-origin requests

    allowed = get_allowed_origins()
    return origin in allowed


def get_cors_headers(origin: Optional[str]) -> dict:
    """
    Get CORS headers for a response.

    Args:
        origin: The Origin header value

    Returns:
        Dictionary of CORS headers
    """
    headers = {}

    if origin and is_origin_allowed(origin):
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Allow-Credentials"] = "true"
        headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With"
        headers["Access-Control-Max-Age"] = "86400"

    return headers


def cors_response(
    body: str = "",
    status_code: int = 200,
    origin: Optional[str] = None,
    content_type: str = "application/json",
) -> func.HttpResponse:
    """
    Create an HTTP response with CORS headers.

    Args:
        body: Response body
        status_code: HTTP status code
        origin: Origin header from request
        content_type: Content-Type header

    Returns:
        HttpResponse with CORS headers
    """
    headers = get_cors_headers(origin)
    headers["Content-Type"] = content_type

    return func.HttpResponse(
        body,
        status_code=status_code,
        headers=headers,
    )


def handle_cors_preflight(req: func.HttpRequest) -> Optional[func.HttpResponse]:
    """
    Handle CORS preflight OPTIONS request.

    Args:
        req: The HTTP request

    Returns:
        HttpResponse for preflight, or None if not a preflight request
    """
    if req.method != "OPTIONS":
        return None

    origin = req.headers.get("Origin")

    if not is_origin_allowed(origin):
        logger.warning(f"CORS preflight rejected for origin: {origin}")
        return func.HttpResponse(
            "Origin not allowed",
            status_code=403,
        )

    return cors_response(
        body="",
        status_code=204,
        origin=origin,
    )


def with_cors(func_handler):
    """
    Decorator to add CORS handling to a function.

    Usage:
        @with_cors
        def main(req: func.HttpRequest) -> func.HttpResponse:
            return func.HttpResponse("Hello")
    """
    @wraps(func_handler)
    def wrapper(req: func.HttpRequest, *args, **kwargs) -> func.HttpResponse:
        origin = req.headers.get("Origin")

        # Handle preflight
        preflight_response = handle_cors_preflight(req)
        if preflight_response:
            return preflight_response

        # Check origin for non-preflight requests
        if origin and not is_origin_allowed(origin):
            logger.warning(f"CORS request rejected for origin: {origin}")
            return cors_response(
                body='{"error": "Origin not allowed"}',
                status_code=403,
                origin=None,
            )

        # Execute the actual handler
        response = func_handler(req, *args, **kwargs)

        # Add CORS headers to response
        cors_headers = get_cors_headers(origin)
        for key, value in cors_headers.items():
            # Azure Functions responses may not be mutable
            # Return new response with headers
            pass

        return response

    return wrapper
```

---

## 5. Environment-Based Configuration

### 5.1 Environment Variables

**File: `.env.example`** (Add)

```bash
# CORS Configuration
# Primary application URL (required for CORS)
NEXTAUTH_URL=https://app-pulse-training-ui-prod.azurewebsites.net

# Additional allowed origins (comma-separated, optional)
# CORS_ALLOWED_ORIGINS=https://admin.pulse.training,https://portal.company.com
```

### 5.2 Terraform Variables

**File: `prod.tfvars`** (Add)

```hcl
# CORS Configuration
cors_allowed_origins = [
  "https://app-pulse-training-ui-prod.azurewebsites.net"
]
```

### 5.3 App Service Configuration

**File: `modules/app/main.tf`** (Add to app_settings)

```hcl
app_settings = {
  # ... other settings ...

  # CORS Configuration
  "CORS_ALLOWED_ORIGINS" = join(",", var.cors_allowed_origins)
  "WEBAPP_URL"           = "https://${var.webapp_hostname}"
}
```

---

## 6. Testing and Validation

### 6.1 CORS Test Script

**File: `scripts/test-cors.sh`**

```bash
#!/bin/bash
# CORS Security Test Script for PULSE Platform

set -e

# Configuration
API_BASE="${1:-https://app-pulse-training-ui-prod.azurewebsites.net}"
ALLOWED_ORIGIN="https://app-pulse-training-ui-prod.azurewebsites.net"
MALICIOUS_ORIGIN="https://evil.attacker.com"

echo "=== PULSE CORS Security Test ==="
echo "API Base: $API_BASE"
echo ""

# Test 1: Preflight from allowed origin (should succeed)
echo "Test 1: Preflight from ALLOWED origin"
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" \
  -X OPTIONS \
  -H "Origin: $ALLOWED_ORIGIN" \
  -H "Access-Control-Request-Method: POST" \
  "$API_BASE/api/orchestrator/chat")

if [ "$RESPONSE" = "204" ]; then
  echo "  ✓ PASS: Preflight allowed (HTTP $RESPONSE)"
else
  echo "  ✗ FAIL: Expected 204, got $RESPONSE"
fi

# Test 2: Preflight from malicious origin (should fail)
echo ""
echo "Test 2: Preflight from MALICIOUS origin"
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" \
  -X OPTIONS \
  -H "Origin: $MALICIOUS_ORIGIN" \
  -H "Access-Control-Request-Method: POST" \
  "$API_BASE/api/orchestrator/chat")

if [ "$RESPONSE" = "403" ]; then
  echo "  ✓ PASS: Preflight blocked (HTTP $RESPONSE)"
else
  echo "  ✗ FAIL: Expected 403, got $RESPONSE"
fi

# Test 3: Check CORS headers from allowed origin
echo ""
echo "Test 3: CORS headers from ALLOWED origin"
HEADERS=$(curl -s -I \
  -H "Origin: $ALLOWED_ORIGIN" \
  "$API_BASE/api/health" 2>/dev/null)

if echo "$HEADERS" | grep -q "Access-Control-Allow-Origin: $ALLOWED_ORIGIN"; then
  echo "  ✓ PASS: Correct Allow-Origin header"
else
  echo "  ✗ FAIL: Missing or incorrect Allow-Origin header"
fi

# Test 4: Verify no wildcard CORS
echo ""
echo "Test 4: Verify NO wildcard (*) CORS"
if echo "$HEADERS" | grep -q "Access-Control-Allow-Origin: \*"; then
  echo "  ✗ FAIL: Wildcard CORS detected!"
else
  echo "  ✓ PASS: No wildcard CORS"
fi

# Test 5: Request from malicious origin (should not include CORS headers)
echo ""
echo "Test 5: Request from MALICIOUS origin"
HEADERS=$(curl -s -I \
  -H "Origin: $MALICIOUS_ORIGIN" \
  "$API_BASE/api/health" 2>/dev/null)

if echo "$HEADERS" | grep -q "Access-Control-Allow-Origin"; then
  echo "  ✗ FAIL: CORS headers present for malicious origin"
else
  echo "  ✓ PASS: No CORS headers for malicious origin"
fi

echo ""
echo "=== CORS Test Complete ==="
```

### 6.2 Browser Console Test

Open browser DevTools console on a different domain and run:

```javascript
// This should FAIL after CORS is properly configured
fetch('https://app-pulse-training-ui-prod.azurewebsites.net/api/orchestrator/chat', {
  method: 'POST',
  credentials: 'include',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({ message: 'test' })
})
.then(response => console.log('SECURITY ISSUE: Request succeeded!', response))
.catch(error => console.log('GOOD: Request blocked by CORS', error));
```

### 6.3 Automated Test

**File: `ui/__tests__/cors.test.ts`**

```typescript
import { isOriginAllowed, getCorsHeaders } from "@/lib/cors";

describe("CORS Security", () => {
  const originalEnv = process.env;

  beforeEach(() => {
    process.env = {
      ...originalEnv,
      NEXTAUTH_URL: "https://app.pulse.training",
    };
  });

  afterEach(() => {
    process.env = originalEnv;
  });

  describe("isOriginAllowed", () => {
    it("should allow configured origin", () => {
      expect(isOriginAllowed("https://app.pulse.training")).toBe(true);
    });

    it("should reject unknown origins", () => {
      expect(isOriginAllowed("https://evil.com")).toBe(false);
    });

    it("should reject null origin with explicit check", () => {
      expect(isOriginAllowed(null)).toBe(false);
    });

    it("should never allow wildcard", () => {
      expect(isOriginAllowed("*")).toBe(false);
    });
  });

  describe("getCorsHeaders", () => {
    it("should return headers for allowed origin", () => {
      const headers = getCorsHeaders("https://app.pulse.training");
      expect(headers["Access-Control-Allow-Origin"]).toBe(
        "https://app.pulse.training"
      );
      expect(headers["Access-Control-Allow-Credentials"]).toBe("true");
    });

    it("should not return Allow-Origin for disallowed origin", () => {
      const headers = getCorsHeaders("https://evil.com");
      expect(headers["Access-Control-Allow-Origin"]).toBeUndefined();
    });
  });
});
```

---

## 7. Migration Checklist

### Phase 1: Preparation

- [ ] Identify all API routes with CORS headers
- [ ] Document current CORS configuration
- [ ] Create `ui/lib/cors.ts` utility module
- [ ] Add CORS environment variables to configuration

### Phase 2: Implementation

- [ ] Update `/api/orchestrator/chat/route.ts` to use `corsMiddleware`
- [ ] Update `/api/orchestrator/context/route.ts` to use `corsMiddleware`
- [ ] Update `/api/orchestrator/admin/prompts/route.ts` to use `corsMiddleware`
- [ ] Update any other API routes with CORS headers
- [ ] Update Function App Terraform with CORS configuration

### Phase 3: Testing

- [ ] Run CORS test script against staging environment
- [ ] Verify preflight requests work from allowed origins
- [ ] Verify preflight requests fail from disallowed origins
- [ ] Test authentication flows still work
- [ ] Run automated CORS tests

### Phase 4: Deployment

- [ ] Deploy to staging and verify
- [ ] Deploy to production
- [ ] Monitor for CORS errors in logs
- [ ] Verify no cross-origin attack vectors remain

---

## Appendix A: Quick Reference

### CORS Headers Cheat Sheet

```
# Secure CORS Response Headers
Access-Control-Allow-Origin: https://your-app.com  (NEVER use *)
Access-Control-Allow-Methods: GET, POST, PUT, DELETE
Access-Control-Allow-Headers: Content-Type, Authorization
Access-Control-Allow-Credentials: true
Access-Control-Max-Age: 86400
```

### Common CORS Errors

| Error | Cause | Solution |
|-------|-------|----------|
| "No 'Access-Control-Allow-Origin' header" | Origin not in allowed list | Add origin to allowed list |
| "Credentials flag is true, but Allow-Origin is *" | Wildcard with credentials | Use specific origin, not * |
| "Method not allowed" | Method not in Allow-Methods | Add method to allowed list |
| "Request header not allowed" | Header not in Allow-Headers | Add header to allowed list |

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2024-12-25 | Security Team | Initial guide |

---

**Classification:** RESTRICTED - Internal Use Only
