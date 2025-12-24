# OIDC Implementation Guide for Next.js Applications with Azure App Service

## Overview

This guide provides a comprehensive implementation plan for adding Microsoft Entra ID (Azure AD) OIDC authentication to Next.js applications deployed on Azure App Service. It incorporates lessons learned from real-world deployment issues and their resolutions.

---

## Table of Contents

1. [Prerequisites Checklist](#prerequisites-checklist)
2. [Azure Infrastructure Setup](#azure-infrastructure-setup)
3. [Application Code Implementation](#application-code-implementation)
4. [Environment Configuration](#environment-configuration)
5. [Deployment Process](#deployment-process)
6. [Validation & Testing](#validation--testing)
7. [Common Issues & Resolutions](#common-issues--resolutions)
8. [OIDC Verification Script](#oidc-verification-script)

---

## Prerequisites Checklist

### Azure Resources Required

- [ ] Azure Subscription with appropriate permissions
- [ ] Resource Group created
- [ ] Azure App Service (Linux, Node.js runtime)
- [ ] Microsoft Entra ID (Azure AD) tenant access
- [ ] Permission to create App Registrations in Entra ID

### Local Development Requirements

- [ ] Node.js 18+ installed
- [ ] Azure CLI installed and authenticated (`az login`)
- [ ] Git repository initialized
- [ ] Next.js 14+ application with App Router

### Entra ID App Registration Prerequisites

Before starting, gather or create:

| Item | Description | Example |
|------|-------------|---------|
| Client ID | Application (client) ID from App Registration | `9196744b-cf41-4197-9361-0eebccb3ffb6` |
| Client Secret | Secret value (not ID) from Certificates & secrets | `xxxxxxxx-xxxx-xxxx-xxxx` |
| Tenant ID | Directory (tenant) ID | `ed8aabd5-14de-4982-9fb6-d6528851af5e` |
| Redirect URI | Callback URL for OIDC flow | `https://your-app.azurewebsites.net/api/auth/callback/azure-ad` |

---

## Azure Infrastructure Setup

### Step 1: Create Entra ID App Registration

```bash
# Create the app registration
az ad app create \
  --display-name "YourApp-OIDC" \
  --sign-in-audience "AzureADMyOrg" \
  --web-redirect-uris "https://your-app.azurewebsites.net/api/auth/callback/azure-ad"

# Get the Application ID
APP_ID=$(az ad app list --display-name "YourApp-OIDC" --query "[0].appId" -o tsv)

# Create a client secret (valid for 2 years)
az ad app credential reset --id $APP_ID --years 2
```

### Step 2: Configure App Registration Permissions

In Azure Portal > Entra ID > App Registrations > Your App:

1. **API Permissions**: Add Microsoft Graph permissions:
   - `openid` (delegated)
   - `profile` (delegated)
   - `email` (delegated)
   - `User.Read` (delegated)

2. **Authentication**:
   - Enable ID tokens
   - Set supported account types (Single tenant recommended for enterprise)

3. **Redirect URIs**: Add both callback formats:
   ```
   https://your-app.azurewebsites.net/api/auth/callback/azure-ad
   https://your-app.azurewebsites.net/api/auth/callback/microsoft-entra-id
   ```

> **CRITICAL**: NextAuth.js uses `azure-ad` as the provider ID, but some configurations use `microsoft-entra-id`. Add both redirect URIs to prevent callback mismatch errors.

### Step 3: Configure Azure App Service

```bash
# Set required environment variables
az webapp config appsettings set \
  --resource-group your-rg \
  --name your-app-name \
  --settings \
    AUTH_MODE="sso" \
    AZURE_AD_CLIENT_ID="your-client-id" \
    AZURE_AD_CLIENT_SECRET="your-client-secret" \
    AZURE_AD_TENANT_ID="your-tenant-id" \
    NEXTAUTH_SECRET="$(openssl rand -base64 32)" \
    NEXTAUTH_URL="https://your-app.azurewebsites.net"
```

---

## Application Code Implementation

### Step 1: Install Dependencies

```bash
npm install next-auth
npm install --save-dev @types/next-auth  # If using TypeScript
```

### Step 2: Create Auth Configuration

Create `lib/auth-config.ts`:

```typescript
// =============================================================================
// Authentication Configuration
// =============================================================================

import type { AuthOptions } from "next-auth";
import AzureADProvider from "next-auth/providers/azure-ad";

// Environment variables - read at module load time for NextAuth
const AZURE_AD_CLIENT_ID = process.env.AZURE_AD_CLIENT_ID || "";
const AZURE_AD_CLIENT_SECRET = process.env.AZURE_AD_CLIENT_SECRET || "";
const AZURE_AD_TENANT_ID = process.env.AZURE_AD_TENANT_ID || "";
const NEXTAUTH_SECRET = process.env.NEXTAUTH_SECRET || "dev-secret-change-in-production";
const AUTH_MODE = process.env.AUTH_MODE || "demo";

// Check if SSO is configured
export const isOIDCConfigured = Boolean(
  AZURE_AD_CLIENT_ID && AZURE_AD_CLIENT_SECRET && AZURE_AD_TENANT_ID
);

export const isSSOEnabled = AUTH_MODE === "sso" && isOIDCConfigured;

// NextAuth configuration
export const authOptions: AuthOptions = {
  providers: isOIDCConfigured
    ? [
        AzureADProvider({
          clientId: AZURE_AD_CLIENT_ID,
          clientSecret: AZURE_AD_CLIENT_SECRET,
          tenantId: AZURE_AD_TENANT_ID,
          authorization: {
            params: {
              scope: "openid profile email User.Read",
            },
          },
          profile(profile) {
            return {
              id: profile.oid || profile.sub,
              name: profile.name || profile.preferred_username,
              email: profile.email || profile.preferred_username,
              image: null,
              entraObjectId: profile.oid,
            };
          },
        }),
      ]
    : [],

  secret: NEXTAUTH_SECRET,

  session: {
    strategy: "jwt",
    maxAge: 8 * 60 * 60, // 8 hours
  },

  pages: {
    signIn: "/",
    error: "/auth/error",
  },

  callbacks: {
    async signIn({ user, account }) {
      if (!user.email) return false;

      // Add custom user validation logic here
      // Example: Check if user exists in your database
      if (isSSOEnabled) {
        try {
          const baseUrl = process.env.NEXTAUTH_URL || "http://localhost:3000";
          const response = await fetch(`${baseUrl}/api/auth/check-user`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              email: user.email,
              name: user.name,
              entraObjectId: account?.providerAccountId,
            }),
          });

          if (!response.ok) {
            const data = await response.json();
            return `/auth/error?error=${encodeURIComponent(data.error || "AccessDenied")}`;
          }

          const userData = await response.json();
          if (userData.status === "pending") {
            return "/auth/pending";
          }
          if (userData.status !== "active") {
            return "/auth/error?error=AccountDisabled";
          }
        } catch (error) {
          console.error("Error checking user:", error);
        }
      }

      return true;
    },

    async jwt({ token, user, account }) {
      if (user) {
        token.id = user.id;
        token.email = user.email;
        token.name = user.name;
        token.entraObjectId = (user as { entraObjectId?: string }).entraObjectId;
      }
      if (account) {
        token.accessToken = account.access_token;
        token.provider = account.provider;
      }

      // Fetch user role from database
      if (user && token.email) {
        try {
          const baseUrl = process.env.NEXTAUTH_URL || "http://localhost:3000";
          const response = await fetch(`${baseUrl}/api/auth/check-user`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email: token.email }),
          });
          if (response.ok) {
            const userData = await response.json();
            // IMPORTANT: Handle nested response structure
            token.role = userData.user?.role || userData.role;
            token.status = userData.user?.status || userData.status;
            token.userId = userData.user?.id || userData.id;
          }
        } catch (error) {
          console.error("Error fetching user role:", error);
        }
      }

      return token;
    },

    async session({ session, token }) {
      if (session.user) {
        const extendedUser = session.user as {
          id?: string;
          email?: string | null;
          name?: string | null;
          entraObjectId?: string;
          provider?: string;
          role?: string;
          status?: string;
          userId?: string;
        };
        extendedUser.id = token.id as string;
        extendedUser.email = token.email as string;
        extendedUser.name = token.name as string;
        extendedUser.entraObjectId = token.entraObjectId as string;
        extendedUser.provider = token.provider as string;
        extendedUser.role = token.role as string;
        extendedUser.status = token.status as string;
        extendedUser.userId = token.userId as string;
      }
      return session;
    },

    async redirect({ url, baseUrl }) {
      if (url.startsWith(baseUrl)) {
        return url;
      }
      return `${baseUrl}/dashboard`; // Default post-login redirect
    },
  },

  debug: process.env.NODE_ENV === "development",
};
```

### Step 3: Create NextAuth API Route

Create `app/api/auth/[...nextauth]/route.ts`:

```typescript
import NextAuth from "next-auth";
import { authOptions } from "@/lib/auth-config";

const handler = NextAuth(authOptions);

export { handler as GET, handler as POST };
```

### Step 4: Create Auth Settings API (Critical for Standalone Builds)

Create `app/api/auth/settings/route.ts`:

```typescript
// =============================================================================
// Auth Settings API - Returns auth configuration to client
// =============================================================================

import { NextResponse } from "next/server";

// CRITICAL: Force dynamic rendering to read env vars at runtime
// Without this, standalone builds will cache build-time values
export const dynamic = "force-dynamic";

export async function GET() {
  // Read AUTH_MODE at runtime, not build time
  const authMode = process.env.AUTH_MODE || "demo";

  return NextResponse.json({
    authMode: authMode === "sso" ? "sso" : "demo",
    ssoEnabled: authMode === "sso",
    requireApproval: true,
    sessionTimeoutMinutes: 480,
  });
}
```

### Step 5: Create OIDC Config API (For Admin Display)

Create `app/api/auth/oidc-config/route.ts`:

```typescript
// =============================================================================
// OIDC Configuration API - Returns OIDC config for admin display
// =============================================================================

import { NextResponse } from "next/server";

// CRITICAL: Force dynamic rendering
export const dynamic = "force-dynamic";

export async function GET() {
  // Read environment variables at runtime
  const clientId = process.env.AZURE_AD_CLIENT_ID || "";
  const tenantId = process.env.AZURE_AD_TENANT_ID || "";
  const clientSecret = process.env.AZURE_AD_CLIENT_SECRET || "";
  const authMode = process.env.AUTH_MODE || "demo";

  const isConfigured = Boolean(clientId && clientSecret && tenantId);

  return NextResponse.json({
    clientId: clientId ? `${clientId.slice(0, 8)}...` : "Not configured",
    tenantId: tenantId || "Not configured",
    issuer: tenantId
      ? `https://login.microsoftonline.com/${tenantId}/v2.0`
      : "Not configured",
    authorizationUrl: tenantId
      ? `https://login.microsoftonline.com/${tenantId}/oauth2/v2.0/authorize`
      : "Not configured",
    tokenUrl: tenantId
      ? `https://login.microsoftonline.com/${tenantId}/oauth2/v2.0/token`
      : "Not configured",
    isConfigured,
    mode: authMode,
  });
}
```

### Step 6: Create Auth Context Provider

Create `components/AuthContext.tsx`:

```typescript
"use client";

import { createContext, useContext, useState, useEffect, ReactNode } from "react";
import { SessionProvider, useSession, signIn, signOut } from "next-auth/react";

interface AuthContextType {
  isAuthenticated: boolean;
  isLoading: boolean;
  user: User | null;
  login: (username: string, password: string) => Promise<boolean>;
  loginWithSSO: () => Promise<void>;
  logout: () => Promise<void>;
  authMode: "demo" | "sso";
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

function AuthProviderInner({ children }: { children: ReactNode }) {
  const { data: session, status } = useSession();
  const [user, setUser] = useState<User | null>(null);
  const [authMode, setAuthMode] = useState<"demo" | "sso">("demo");
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    async function initialize() {
      setIsLoading(true);
      try {
        // IMPORTANT: Fetch auth settings from API, not static config
        const response = await fetch("/api/auth/settings");
        if (response.ok) {
          const settings = await response.json();
          setAuthMode(settings.authMode);
        }

        // Handle SSO session
        if (status === "authenticated" && session?.user?.email) {
          // Fetch user from your database
          setUser(session.user as User);
        }
      } catch (error) {
        console.error("Error initializing auth:", error);
      }
      setIsLoading(false);
    }

    if (status !== "loading") {
      initialize();
    }
  }, [session, status]);

  const loginWithSSO = async () => {
    await signIn("azure-ad", { callbackUrl: "/dashboard" });
  };

  const logout = async () => {
    setUser(null);
    if (session) {
      await signOut({ callbackUrl: "/" });
    }
  };

  return (
    <AuthContext.Provider
      value={{
        isAuthenticated: !!user,
        isLoading: isLoading || status === "loading",
        user,
        login: async () => false, // Implement for demo mode
        loginWithSSO,
        logout,
        authMode,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function AuthProvider({ children }: { children: ReactNode }) {
  return (
    <SessionProvider>
      <AuthProviderInner>{children}</AuthProviderInner>
    </SessionProvider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
```

### Step 7: Configure Next.js for Standalone Output

Update `next.config.mjs`:

```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  reactStrictMode: true,
};

export default nextConfig;
```

---

## Environment Configuration

### Required Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `AUTH_MODE` | `"sso"` or `"demo"` | Yes |
| `AZURE_AD_CLIENT_ID` | Entra ID App Client ID | Yes (for SSO) |
| `AZURE_AD_CLIENT_SECRET` | Entra ID App Client Secret | Yes (for SSO) |
| `AZURE_AD_TENANT_ID` | Entra ID Tenant ID | Yes (for SSO) |
| `NEXTAUTH_SECRET` | Random string for JWT signing | Yes |
| `NEXTAUTH_URL` | Full URL of your application | Yes |

### Local Development (.env.local)

```bash
AUTH_MODE=demo
AZURE_AD_CLIENT_ID=your-client-id
AZURE_AD_CLIENT_SECRET=your-client-secret
AZURE_AD_TENANT_ID=your-tenant-id
NEXTAUTH_SECRET=your-random-secret-at-least-32-chars
NEXTAUTH_URL=http://localhost:3000
```

### Production (Azure App Service)

```bash
az webapp config appsettings set \
  --resource-group your-rg \
  --name your-app \
  --settings \
    AUTH_MODE="sso" \
    AZURE_AD_CLIENT_ID="..." \
    AZURE_AD_CLIENT_SECRET="..." \
    AZURE_AD_TENANT_ID="..." \
    NEXTAUTH_SECRET="$(openssl rand -base64 32)" \
    NEXTAUTH_URL="https://your-app.azurewebsites.net"
```

---

## Deployment Process

### Critical Deployment Steps for Next.js Standalone

The standalone build requires special handling for Azure App Service:

```bash
# 1. Build the application
npm run build

# 2. Create deployment directory
rm -rf /tmp/deploy && mkdir -p /tmp/deploy

# 3. Copy standalone output (CRITICAL: use 'cp -R .' to include hidden directories)
cd .next/standalone && cp -R . /tmp/deploy/

# 4. Copy static assets (NOT included in standalone by default)
cp -R .next/static /tmp/deploy/.next/static

# 5. Create deployment package
cd /tmp/deploy && zip -rq /tmp/deploy.zip . -x "*.DS_Store"

# 6. Deploy to Azure
az webapp deploy \
  --resource-group your-rg \
  --name your-app \
  --src-path /tmp/deploy.zip \
  --type zip \
  --clean true
```

> **CRITICAL LESSON LEARNED**: Using `cp -R *` does NOT copy the `.next` directory because it's hidden. Always use `cp -R .` from within the source directory.

### Deployment Script

Create `scripts/deploy.sh`:

```bash
#!/bin/bash
set -e

RESOURCE_GROUP="${1:-your-default-rg}"
APP_NAME="${2:-your-default-app}"

echo "Building Next.js application..."
npm run build

echo "Creating deployment package..."
rm -rf /tmp/deploy && mkdir -p /tmp/deploy
cd .next/standalone && cp -R . /tmp/deploy/
cp -R ../../.next/static /tmp/deploy/.next/static

echo "Creating zip archive..."
cd /tmp/deploy && rm -f /tmp/deploy.zip && zip -rq /tmp/deploy.zip . -x "*.DS_Store"

echo "Deploying to Azure App Service..."
az webapp deploy \
  --resource-group "$RESOURCE_GROUP" \
  --name "$APP_NAME" \
  --src-path /tmp/deploy.zip \
  --type zip \
  --clean true

echo "Deployment complete!"
echo "Visit: https://${APP_NAME}.azurewebsites.net"
```

---

## Validation & Testing

### Pre-Deployment Checklist

- [ ] All environment variables set in Azure App Service
- [ ] Redirect URIs configured in Entra ID (both `azure-ad` and `microsoft-entra-id` formats)
- [ ] API permissions granted in Entra ID
- [ ] `.next/standalone/.next` directory contains `routes-manifest.json`
- [ ] Static assets copied to `.next/static`

### Post-Deployment Verification

```bash
# 1. Check app is running
curl -s -o /dev/null -w "%{http_code}" https://your-app.azurewebsites.net/

# 2. Check auth settings API
curl -s https://your-app.azurewebsites.net/api/auth/settings

# 3. Check OIDC config API
curl -s https://your-app.azurewebsites.net/api/auth/oidc-config

# 4. Check NextAuth providers
curl -s https://your-app.azurewebsites.net/api/auth/providers

# 5. Check NextAuth session
curl -s https://your-app.azurewebsites.net/api/auth/session
```

---

## Common Issues & Resolutions

### Issue 1: "Could not find a production build in './.next' directory"

**Cause**: The `.next` directory wasn't copied properly during deployment.

**Solution**: Use `cp -R .` instead of `cp -R *` to include hidden directories:
```bash
cd .next/standalone && cp -R . /tmp/deploy/
```

### Issue 2: Auth Settings API Returns "demo" When AUTH_MODE is "sso"

**Cause**: Environment variables read at build time instead of runtime.

**Solution**: Add `export const dynamic = "force-dynamic"` to API routes:
```typescript
export const dynamic = "force-dynamic";

export async function GET() {
  const authMode = process.env.AUTH_MODE || "demo"; // Now reads at runtime
  // ...
}
```

### Issue 3: Redirect URI Mismatch Error (AADSTS50011)

**Cause**: NextAuth uses `azure-ad` as provider ID, but some configs expect `microsoft-entra-id`.

**Solution**: Add both redirect URIs to Entra ID App Registration:
```bash
az ad app update --id YOUR_APP_ID --web-redirect-uris \
  "https://your-app.azurewebsites.net/api/auth/callback/azure-ad" \
  "https://your-app.azurewebsites.net/api/auth/callback/microsoft-entra-id"
```

### Issue 4: User Role Not Set Correctly After Login

**Cause**: JWT callback reading wrong property path from API response.

**Solution**: Handle nested response structure:
```typescript
// API returns: { user: { role: "admin" } }
// Callback should read:
token.role = userData.user?.role || userData.role;
```

### Issue 5: Loading Spinner Forever on Login Page

**Cause**: `getAuthSettings()` failing silently on client side.

**Solution**: Create `/api/auth/settings` endpoint that clients can fetch from, instead of reading environment variables directly.

### Issue 6: Azure Cognitive Services 403 "Public access is disabled"

**Cause**: Speech/AI services configured with private endpoint only.

**Solution**: Enable public network access:
```bash
az resource update \
  --ids "/subscriptions/.../providers/Microsoft.CognitiveServices/accounts/your-service" \
  --set properties.publicNetworkAccess=Enabled
```

---

## OIDC Verification Script

Create `scripts/verify-oidc.sh`:

```bash
#!/bin/bash
# =============================================================================
# OIDC Configuration Verification Script
# =============================================================================

set -e

# Configuration - Update these values
EXPECTED_CLIENT_ID="${AZURE_AD_CLIENT_ID:-your-client-id}"
EXPECTED_TENANT_ID="${AZURE_AD_TENANT_ID:-your-tenant-id}"
RESOURCE_GROUP="${RESOURCE_GROUP:-your-resource-group}"
WEB_APP_NAME="${WEB_APP_NAME:-your-app-name}"
APP_URL="${APP_URL:-https://${WEB_APP_NAME}.azurewebsites.net}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "=============================================="
echo "OIDC Configuration Verification"
echo "=============================================="
echo ""

ERRORS=0
WARNINGS=0

# Function to check status
check() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}[PASS]${NC} $2"
    else
        echo -e "${RED}[FAIL]${NC} $2"
        ERRORS=$((ERRORS + 1))
    fi
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
    WARNINGS=$((WARNINGS + 1))
}

info() {
    echo -e "       $1"
}

# =============================================================================
# 1. Check Azure CLI Authentication
# =============================================================================
echo "--- Azure CLI Authentication ---"
az account show > /dev/null 2>&1
check $? "Azure CLI authenticated"

# =============================================================================
# 2. Check Entra ID App Registration
# =============================================================================
echo ""
echo "--- Entra ID App Registration ---"

APP_INFO=$(az ad app show --id "$EXPECTED_CLIENT_ID" 2>/dev/null || echo "NOT_FOUND")

if [ "$APP_INFO" != "NOT_FOUND" ]; then
    check 0 "App registration found: $EXPECTED_CLIENT_ID"

    # Check redirect URIs
    REDIRECT_URIS=$(echo "$APP_INFO" | jq -r '.web.redirectUris[]' 2>/dev/null)

    if echo "$REDIRECT_URIS" | grep -q "callback/azure-ad"; then
        check 0 "Redirect URI for azure-ad callback configured"
    else
        check 1 "Missing redirect URI: .../api/auth/callback/azure-ad"
    fi

    if echo "$REDIRECT_URIS" | grep -q "callback/microsoft-entra-id"; then
        check 0 "Redirect URI for microsoft-entra-id callback configured"
    else
        warn "Missing redirect URI: .../api/auth/callback/microsoft-entra-id (optional but recommended)"
    fi
else
    check 1 "App registration not found: $EXPECTED_CLIENT_ID"
fi

# =============================================================================
# 3. Check Azure App Service Configuration
# =============================================================================
echo ""
echo "--- Azure App Service Configuration ---"

APP_SETTINGS=$(az webapp config appsettings list \
    --resource-group "$RESOURCE_GROUP" \
    --name "$WEB_APP_NAME" \
    -o json 2>/dev/null || echo "[]")

# Check required settings
check_setting() {
    local name=$1
    local expected=$2
    local value=$(echo "$APP_SETTINGS" | jq -r ".[] | select(.name==\"$name\") | .value")

    if [ -z "$value" ]; then
        check 1 "$name not configured"
    elif [ -n "$expected" ] && [ "$value" != "$expected" ]; then
        check 1 "$name value mismatch (expected: $expected)"
    else
        check 0 "$name configured"
    fi
}

check_setting "AUTH_MODE" "sso"
check_setting "AZURE_AD_CLIENT_ID" ""
check_setting "AZURE_AD_CLIENT_SECRET" ""
check_setting "AZURE_AD_TENANT_ID" ""
check_setting "NEXTAUTH_SECRET" ""
check_setting "NEXTAUTH_URL" ""

# =============================================================================
# 4. Check Application Endpoints
# =============================================================================
echo ""
echo "--- Application Endpoints ---"

# Check main app
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$APP_URL/" 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "200" ]; then
    check 0 "Application responding (HTTP $HTTP_CODE)"
else
    check 1 "Application not responding (HTTP $HTTP_CODE)"
fi

# Check auth settings API
AUTH_SETTINGS=$(curl -s "$APP_URL/api/auth/settings" 2>/dev/null)
AUTH_MODE=$(echo "$AUTH_SETTINGS" | jq -r '.authMode' 2>/dev/null)

if [ "$AUTH_MODE" = "sso" ]; then
    check 0 "Auth settings API returning SSO mode"
elif [ "$AUTH_MODE" = "demo" ]; then
    check 1 "Auth settings API returning demo mode (should be sso)"
    info "This usually means AUTH_MODE env var is not being read at runtime"
    info "Ensure API route has: export const dynamic = 'force-dynamic'"
else
    check 1 "Auth settings API not responding correctly"
fi

# Check OIDC config API
OIDC_CONFIG=$(curl -s "$APP_URL/api/auth/oidc-config" 2>/dev/null)
IS_CONFIGURED=$(echo "$OIDC_CONFIG" | jq -r '.isConfigured' 2>/dev/null)

if [ "$IS_CONFIGURED" = "true" ]; then
    check 0 "OIDC config API shows configured"
else
    check 1 "OIDC config API shows not configured"
fi

# Check NextAuth providers
PROVIDERS=$(curl -s "$APP_URL/api/auth/providers" 2>/dev/null)
HAS_AZURE=$(echo "$PROVIDERS" | jq -r '."azure-ad"' 2>/dev/null)

if [ "$HAS_AZURE" != "null" ] && [ -n "$HAS_AZURE" ]; then
    check 0 "NextAuth azure-ad provider registered"
else
    check 1 "NextAuth azure-ad provider not found"
fi

# =============================================================================
# 5. Test Token Endpoint (Optional)
# =============================================================================
echo ""
echo "--- Microsoft Endpoints ---"

TOKEN_URL="https://login.microsoftonline.com/$EXPECTED_TENANT_ID/oauth2/v2.0/token"
TOKEN_CHECK=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$TOKEN_URL" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "client_id=invalid" 2>/dev/null || echo "000")

if [ "$TOKEN_CHECK" = "400" ] || [ "$TOKEN_CHECK" = "401" ]; then
    check 0 "Microsoft token endpoint reachable"
else
    check 1 "Microsoft token endpoint not reachable (HTTP $TOKEN_CHECK)"
fi

# =============================================================================
# Summary
# =============================================================================
echo ""
echo "=============================================="
echo "Summary"
echo "=============================================="
echo -e "Errors:   ${RED}$ERRORS${NC}"
echo -e "Warnings: ${YELLOW}$WARNINGS${NC}"
echo ""

if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}OIDC configuration appears correct!${NC}"
    exit 0
else
    echo -e "${RED}OIDC configuration has issues that need to be resolved.${NC}"
    exit 1
fi
```

Make executable:
```bash
chmod +x scripts/verify-oidc.sh
```

Usage:
```bash
# Set environment variables first
export AZURE_AD_CLIENT_ID="your-client-id"
export AZURE_AD_TENANT_ID="your-tenant-id"
export RESOURCE_GROUP="your-rg"
export WEB_APP_NAME="your-app"

# Run verification
./scripts/verify-oidc.sh
```

---

## Quick Reference

### Commands Cheat Sheet

```bash
# Check app settings
az webapp config appsettings list --resource-group RG --name APP -o table

# Update redirect URIs
az ad app update --id CLIENT_ID --web-redirect-uris "URI1" "URI2"

# Generate NEXTAUTH_SECRET
openssl rand -base64 32

# View app logs
az webapp log tail --resource-group RG --name APP

# Download logs
az webapp log download --resource-group RG --name APP --log-file /tmp/logs.zip

# Check deployment status
az webapp show --resource-group RG --name APP --query "state" -o tsv

# Test endpoints
curl -s https://APP.azurewebsites.net/api/auth/settings | jq
curl -s https://APP.azurewebsites.net/api/auth/oidc-config | jq
curl -s https://APP.azurewebsites.net/api/auth/providers | jq
```

### Key Files Reference

| File | Purpose |
|------|---------|
| `lib/auth-config.ts` | NextAuth configuration |
| `app/api/auth/[...nextauth]/route.ts` | NextAuth API route |
| `app/api/auth/settings/route.ts` | Runtime auth settings |
| `app/api/auth/oidc-config/route.ts` | OIDC config for admin display |
| `components/AuthContext.tsx` | Client-side auth context |
| `next.config.mjs` | Next.js config (standalone output) |
| `scripts/verify-oidc.sh` | Verification script |
| `scripts/deploy.sh` | Deployment script |

---

## Appendix: Troubleshooting Flowchart

```
Login Not Working?
       │
       ├── 503 Error?
       │      └── Check Azure logs: az webapp log tail
       │             ├── "routes-manifest.json" missing?
       │             │      └── Fix: Use 'cp -R .' for deployment
       │             └── App crashing?
       │                    └── Check startup command and node version
       │
       ├── Redirect URI Mismatch?
       │      └── Add both callback URIs to Entra ID App Registration
       │
       ├── Loading Forever?
       │      └── Check /api/auth/settings returns correct authMode
       │             └── Add 'export const dynamic = "force-dynamic"'
       │
       ├── Wrong Role After Login?
       │      └── Check JWT callback reads userData.user.role (nested)
       │
       └── OIDC Shows "Not Configured"?
               └── Create /api/auth/oidc-config with dynamic export
```

---

*Document Version: 1.0*
*Last Updated: December 2024*
*Based on: PULSE Training App OIDC Implementation*
