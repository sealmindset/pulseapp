# PULSE Security Hardening - Developer Implementation Plan

> **Document Version:** 1.1
> **Created:** December 25, 2024
> **Target:** January 7, 2026 Hackathon
> **Scope:** Application-level security fixes (no Azure Portal/cross-team dependencies)
> **Philosophy:** Minimal effective safeguards - protect without restricting legitimate use
> **Classification:** INTERNAL

---

## Executive Summary

This document provides a practical, minimal-but-effective security hardening plan. The goal is to mitigate real risks without over-engineering or breaking the app's core functionality, especially Azure OpenAI interactions.

**Design Principles:**
- **Minimal effective controls** - Just enough security, not maximum security
- **Don't break the demo** - All controls must preserve normal app operation
- **Log, don't block** (where appropriate) - Monitor suspicious activity rather than blocking legitimate use
- **Fail open for AI** - Prompt security should warn/log, not block conversations

**Total Estimated Effort:** ~12 hours (reduced from 21.5h)

| Priority | Security Fix | Effort | Approach |
|----------|--------------|--------|----------|
| Critical | CORS Hardening | 1h | Simple origin allowlist |
| Critical | Prompt Injection Protection | 1.5h | **Logging only** - monitor, don't block |
| High | Input Validation | 1.5h | Basic length/format checks only |
| High | Rate Limiting | 1.5h | Generous limits, protect costs only |
| High | Session Security | 1h | Check status on sensitive actions |
| Medium | Security Headers | 0.5h | Standard headers, permissive CSP |
| Medium | Git Hygiene | 0.5h | Update .gitignore |
| Medium | Function App Shared Secret | 1.5h | Simple header validation |
| Medium | Error Sanitization | 1h | Hide stack traces in production |
| Medium | Audit Logging | 2h | Key events only |

---

## Implementation Details

---

### 1. CORS Hardening

**Effort:** 1 hour
**Approach:** Simple origin allowlist - allow the app's own domain and Azure domains

#### Implementation

**File:** `ui/lib/cors.ts`

```typescript
// =============================================================================
// PULSE CORS Configuration
// Simple, permissive approach - just prevent random third-party sites
// =============================================================================

/**
 * Get the allowed origin for CORS.
 * Allows same-origin and Azure domains.
 */
export function getAllowedOrigin(requestOrigin: string | null): string {
  // In development, allow anything
  if (process.env.NODE_ENV === 'development') {
    return requestOrigin || '*';
  }

  // Production: allow our domains and Azure
  const allowedPatterns = [
    'https://app-pulse-training-ui-prod.azurewebsites.net',
    /\.azurewebsites\.net$/,
    /\.azure\.com$/,
  ];

  if (requestOrigin) {
    for (const pattern of allowedPatterns) {
      if (typeof pattern === 'string' && requestOrigin === pattern) {
        return requestOrigin;
      }
      if (pattern instanceof RegExp && pattern.test(requestOrigin)) {
        return requestOrigin;
      }
    }
  }

  // Default to our app URL
  return process.env.NEXT_PUBLIC_APP_URL || 'https://app-pulse-training-ui-prod.azurewebsites.net';
}

/**
 * Standard CORS headers
 */
export function getCorsHeaders(requestOrigin: string | null): Record<string, string> {
  return {
    'Access-Control-Allow-Origin': getAllowedOrigin(requestOrigin),
    'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    'Access-Control-Max-Age': '86400',
  };
}

/**
 * Create OPTIONS response for preflight
 */
export function corsOptionsResponse(req: Request): Response {
  const origin = req.headers.get('origin');
  return new Response(null, {
    status: 204,
    headers: getCorsHeaders(origin),
  });
}
```

#### Update API Routes

Apply to routes - simple pattern:

```typescript
// In any API route
import { getCorsHeaders, corsOptionsResponse } from "@/lib/cors";

export async function OPTIONS(req: Request) {
  return corsOptionsResponse(req);
}

export async function POST(req: Request) {
  const origin = req.headers.get("origin");

  // ... your logic ...

  return new Response(body, {
    status: 200,
    headers: {
      "Content-Type": "application/json",
      ...getCorsHeaders(origin),
    },
  });
}
```

---

### 2. Prompt Injection Protection

**Effort:** 1.5 hours
**Approach:** **MONITOR ONLY** - Log suspicious patterns but NEVER block. The AI can handle itself.

> **Important:** Azure OpenAI has built-in content filtering. We add monitoring for visibility, not blocking.

#### Implementation

**File:** `orchestrator/shared_code/prompt_monitor.py`

```python
"""
Prompt Injection MONITORING for PULSE Platform.

DESIGN PHILOSOPHY:
- We LOG suspicious patterns for visibility
- We NEVER block messages - the AI can handle edge cases
- Azure OpenAI's content filters are the real protection
- This is for awareness and post-incident analysis only
"""

import re
import logging
from typing import List, Tuple

# Patterns that MIGHT indicate injection attempts
# These are for LOGGING only - not blocking
SUSPICIOUS_PATTERNS: List[Tuple[str, str]] = [
    (r'ignore\s+(all\s+)?(previous|prior)', 'instruction_override'),
    (r'system\s*prompt', 'prompt_extraction'),
    (r'you\s+are\s+now', 'role_change'),
    (r'\[INST\]', 'delimiter'),
    (r'DAN\s+mode', 'jailbreak'),
]


def log_if_suspicious(user_message: str, session_id: str) -> None:
    """
    Check message for suspicious patterns and LOG (not block).

    Args:
        user_message: The user's message
        session_id: For correlation in logs
    """
    if not user_message:
        return

    message_lower = user_message.lower()
    detected = []

    for pattern, category in SUSPICIOUS_PATTERNS:
        if re.search(pattern, message_lower, re.IGNORECASE):
            detected.append(category)

    if detected:
        # Log for monitoring - but DO NOT block
        logging.info(
            "PROMPT_MONITOR: session=%s categories=%s preview='%s'",
            session_id,
            detected,
            user_message[:50].replace('\n', ' ')
        )


def wrap_system_prompt(base_prompt: str, persona_type: str) -> str:
    """
    Add minimal protective framing to system prompt.

    This is NOT about blocking - it's about guiding the AI
    to stay in character naturally.
    """
    return f"""You are a {persona_type} customer in a sales training simulation.

{base_prompt}

Stay in character as a customer. If the trainee says something confusing or off-topic,
respond as a real customer would - with confusion or by steering back to the sale.
"""
```

#### Update Chat Handler

**File:** `orchestrator/chat/__init__.py` - minimal change

```python
# Add at the top
from shared_code.prompt_monitor import log_if_suspicious, wrap_system_prompt

# In main(), after getting the message:
message = body.get("message", "").strip()

# Log suspicious patterns (does NOT block)
log_if_suspicious(message, session_id)

# ... rest of existing code unchanged ...
```

#### Update OpenAI Client

**File:** `orchestrator/shared_code/openai_client.py` - minimal change

```python
from shared_code.prompt_monitor import wrap_system_prompt

def generate_conversation_response(...):
    # Use wrapped system prompt
    system_prompt = wrap_system_prompt(
        base_prompt="""Based on the Platinum Rule behavioral styles, respond as this customer type.
Keep responses concise (1-3 sentences) to simulate natural conversation.""",
        persona_type=persona_type
    )

    # ... rest unchanged ...
```

**That's it.** No blocking, no sanitization of user messages, no complex detection. Just logging for visibility.

---

### 3. Input Validation

**Effort:** 1.5 hours
**Approach:** Basic sanity checks only - length limits and format validation

#### Implementation

**File:** `ui/lib/validation.ts`

```typescript
// =============================================================================
// PULSE Input Validation
// Basic sanity checks - not security theater
// =============================================================================

/**
 * Validate UUID format
 */
export function isValidUUID(value: string): boolean {
  const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
  return uuidRegex.test(value);
}

/**
 * Validate chat message
 * Just basic length check - let the AI handle content
 */
export function validateChatMessage(message: string): { valid: boolean; error?: string } {
  if (!message || message.trim().length === 0) {
    return { valid: false, error: 'Message cannot be empty' };
  }

  if (message.length > 5000) {
    return { valid: false, error: 'Message too long (max 5000 characters)' };
  }

  return { valid: true };
}

/**
 * Validate persona type
 */
export function isValidPersona(persona: string): boolean {
  return ['Director', 'Relater', 'Socializer', 'Thinker'].includes(persona);
}

/**
 * Validate session start request
 */
export function validateSessionStart(body: unknown): { valid: boolean; error?: string } {
  if (!body || typeof body !== 'object') {
    return { valid: false, error: 'Invalid request body' };
  }

  const { persona } = body as { persona?: string };

  if (persona && !isValidPersona(persona)) {
    return { valid: false, error: 'Invalid persona type' };
  }

  return { valid: true };
}

/**
 * Validate chat request
 */
export function validateChatRequest(body: unknown): { valid: boolean; error?: string } {
  if (!body || typeof body !== 'object') {
    return { valid: false, error: 'Invalid request body' };
  }

  const { sessionId, message, persona } = body as {
    sessionId?: string;
    message?: string;
    persona?: string
  };

  if (!sessionId || !isValidUUID(sessionId)) {
    return { valid: false, error: 'Invalid session ID' };
  }

  const messageValidation = validateChatMessage(message || '');
  if (!messageValidation.valid) {
    return messageValidation;
  }

  if (persona && !isValidPersona(persona)) {
    return { valid: false, error: 'Invalid persona type' };
  }

  return { valid: true };
}
```

#### Usage in Routes

```typescript
import { validateChatRequest } from "@/lib/validation";

export async function POST(req: Request) {
  const body = await req.json();

  const validation = validateChatRequest(body);
  if (!validation.valid) {
    return new Response(JSON.stringify({ error: validation.error }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }

  // ... proceed with request ...
}
```

---

### 4. Rate Limiting

**Effort:** 1.5 hours
**Approach:** Generous limits focused on cost protection, not security theater

#### Implementation

**File:** `ui/lib/rate-limiter.ts`

```typescript
// =============================================================================
// PULSE Rate Limiting
// Generous limits - protect against cost explosion, not legitimate use
// =============================================================================

interface RateLimitEntry {
  count: number;
  windowStart: number;
}

const store = new Map<string, RateLimitEntry>();

// Generous limits - these should NEVER impact normal usage
const LIMITS = {
  // Chat: 60 requests per minute per user (1 per second average)
  // Normal user sends maybe 10-20 messages in a session
  chat: { windowMs: 60000, max: 60 },

  // Session start: 10 per minute (very generous)
  session: { windowMs: 60000, max: 10 },

  // Default: 120 per minute
  default: { windowMs: 60000, max: 120 },
};

/**
 * Check rate limit - returns true if allowed
 */
export function checkRateLimit(
  identifier: string,
  endpoint: 'chat' | 'session' | 'default' = 'default'
): { allowed: boolean; remaining: number } {
  const config = LIMITS[endpoint];
  const key = `${endpoint}:${identifier}`;
  const now = Date.now();

  let entry = store.get(key);

  if (!entry || (now - entry.windowStart) >= config.windowMs) {
    entry = { count: 0, windowStart: now };
    store.set(key, entry);
  }

  entry.count++;

  return {
    allowed: entry.count <= config.max,
    remaining: Math.max(0, config.max - entry.count),
  };
}

/**
 * Get client identifier from request
 */
export function getClientId(req: Request, userId?: string): string {
  if (userId) return `user:${userId}`;

  const forwarded = req.headers.get('x-forwarded-for');
  if (forwarded) return `ip:${forwarded.split(',')[0].trim()}`;

  return 'anonymous';
}

/**
 * Rate limit middleware helper
 */
export function rateLimitResponse(): Response {
  return new Response(
    JSON.stringify({
      error: 'Too many requests',
      message: 'Please slow down and try again in a moment'
    }),
    {
      status: 429,
      headers: {
        'Content-Type': 'application/json',
        'Retry-After': '60',
      }
    }
  );
}
```

#### Usage

```typescript
import { checkRateLimit, getClientId, rateLimitResponse } from "@/lib/rate-limiter";

export async function POST(req: Request) {
  const clientId = getClientId(req);
  const { allowed } = checkRateLimit(clientId, 'chat');

  if (!allowed) {
    return rateLimitResponse();
  }

  // ... proceed ...
}
```

---

### 5. Session Security

**Effort:** 1 hour
**Approach:** Check user status on admin actions only, not every request

#### Implementation

Update `ui/lib/auth-utils.ts`:

```typescript
/**
 * Require admin auth with fresh status check
 * Only used for sensitive admin operations
 */
export async function requireAdminFresh(): Promise<
  | { session: AuthSession; error: null }
  | { session: null; error: NextResponse }
> {
  const authResult = await requireAdmin();
  if (authResult.error) return authResult;

  // Fresh check for admin operations
  const { session } = authResult;
  if (session.user.email) {
    try {
      const baseUrl = process.env.NEXTAUTH_URL || "http://localhost:3000";
      const response = await fetch(`${baseUrl}/api/auth/check-user`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: session.user.email }),
      });

      if (response.ok) {
        const data = await response.json();
        const user = data.user || data;

        if (user.status !== 'active') {
          return {
            session: null,
            error: NextResponse.json(
              { error: "Account disabled" },
              { status: 403 }
            ),
          };
        }
      }
    } catch {
      // On error, allow with cached session (fail open)
    }
  }

  return { session, error: null };
}
```

Use `requireAdminFresh()` only for:
- User management (create, update, delete users)
- System settings changes
- Prompt management

Regular session checks (`requireAuth()`) remain unchanged for normal operations.

---

### 6. Security Headers

**Effort:** 0.5 hours
**Approach:** Standard headers with permissive CSP that won't break functionality

#### Implementation

**File:** `ui/next.config.mjs`

```javascript
/** @type {import('next').NextConfig} */

const securityHeaders = [
  { key: 'X-Frame-Options', value: 'SAMEORIGIN' },
  { key: 'X-Content-Type-Options', value: 'nosniff' },
  { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
  // Permissive CSP - don't break anything
  {
    key: 'Content-Security-Policy',
    value: [
      "default-src 'self'",
      "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' data: https: blob:",
      "font-src 'self' data:",
      "connect-src 'self' https: wss:",
      "frame-src 'self' https:",
    ].join('; ')
  },
];

const nextConfig = {
  output: 'standalone',
  reactStrictMode: true,
  poweredByHeader: false,

  async headers() {
    return [{ source: '/:path*', headers: securityHeaders }];
  },

  images: {
    remotePatterns: [{ protocol: 'https', hostname: '**' }],
  },
};

export default nextConfig;
```

---

### 7. Git Hygiene

**Effort:** 0.5 hours
**Approach:** Ensure sensitive files are gitignored

#### Implementation

Add to `.gitignore` if not already present:

```gitignore
# Secrets
.env
.env.*
!.env.example
*.tfvars
!*.tfvars.example
*.tfstate
*.tfstate.*
.terraform/
*.pem
*.key
```

Create `.env.example` and `prod.tfvars.example` with placeholder values for documentation.

---

### 8. Function App Shared Secret

**Effort:** 1.5 hours
**Approach:** Simple shared secret for defense-in-depth

#### Implementation

**File:** `orchestrator/shared_code/auth.py`

```python
"""
Simple shared secret validation for Function App.
Defense-in-depth - the UI already authenticates users.
"""

import os
import hmac
import logging
import azure.functions as func


def validate_shared_secret(req: func.HttpRequest) -> bool:
    """
    Validate X-Function-Key header matches our secret.
    Returns True if valid OR if no secret is configured (dev mode).
    """
    expected = os.environ.get('FUNCTION_APP_SHARED_SECRET', '')

    # No secret configured = skip validation (development)
    if not expected:
        return True

    provided = req.headers.get('X-Function-Key', '')

    if not provided:
        logging.warning("Missing X-Function-Key header")
        return False

    # Constant-time comparison
    return hmac.compare_digest(expected, provided)


def require_auth(func_handler):
    """Decorator to require shared secret."""
    def wrapper(req: func.HttpRequest, *args, **kwargs):
        # Skip for OPTIONS (CORS preflight)
        if req.method == "OPTIONS":
            return func_handler(req, *args, **kwargs)

        if not validate_shared_secret(req):
            return func.HttpResponse(
                '{"error": "Unauthorized"}',
                status_code=401,
                mimetype="application/json"
            )

        return func_handler(req, *args, **kwargs)

    return wrapper
```

#### Apply to Functions

```python
from shared_code.auth import require_auth

@require_auth
def main(req: func.HttpRequest) -> func.HttpResponse:
    # ... existing code ...
```

#### UI Side

Add header to Function App calls:

```typescript
const res = await fetch(target, {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "X-Function-Key": process.env.FUNCTION_APP_SHARED_SECRET || "",
  },
  body: JSON.stringify(json),
});
```

#### Configure Secret

```bash
# Generate
SECRET=$(openssl rand -base64 32)

# Set on both apps
az webapp config appsettings set --resource-group rg-PULSE-training-prod \
  --name app-PULSE-training-ui-prod --settings FUNCTION_APP_SHARED_SECRET="$SECRET"

az functionapp config appsettings set --resource-group rg-PULSE-training-prod \
  --name func-PULSE-training-orchestrator-prod --settings FUNCTION_APP_SHARED_SECRET="$SECRET"
```

---

### 9. Error Sanitization

**Effort:** 1 hour
**Approach:** Hide internal details in production, show everything in development

#### Implementation

**File:** `ui/lib/errors.ts`

```typescript
// =============================================================================
// PULSE Error Handling
// Hide internals in production, verbose in development
// =============================================================================

/**
 * Get a safe error message for the client
 */
export function getSafeErrorMessage(error: unknown): string {
  // In development, show everything
  if (process.env.NODE_ENV === 'development') {
    return error instanceof Error ? error.message : String(error);
  }

  // In production, generic messages
  if (error instanceof Error) {
    const msg = error.message.toLowerCase();

    if (msg.includes('timeout')) return 'Request timed out. Please try again.';
    if (msg.includes('network') || msg.includes('fetch')) return 'Network error. Please check your connection.';
    if (msg.includes('unauthorized')) return 'Please sign in to continue.';
    if (msg.includes('forbidden')) return 'You do not have permission for this action.';
  }

  return 'Something went wrong. Please try again.';
}

/**
 * Log error with details, return safe response
 */
export function handleApiError(error: unknown, context: string): Response {
  // Always log full error server-side
  console.error(`[${context}]`, error);

  return new Response(
    JSON.stringify({ error: getSafeErrorMessage(error) }),
    { status: 500, headers: { 'Content-Type': 'application/json' } }
  );
}
```

#### Usage

```typescript
import { handleApiError } from "@/lib/errors";

export async function POST(req: Request) {
  try {
    // ... your logic ...
  } catch (error) {
    return handleApiError(error, 'api/orchestrator/chat');
  }
}
```

---

### 10. Audit Logging

**Effort:** 2 hours
**Approach:** Log key events only - auth, admin actions, errors

#### Implementation

**File:** `ui/lib/audit.ts`

```typescript
// =============================================================================
// PULSE Audit Logging
// Simple structured logging for key events
// =============================================================================

type AuditAction =
  | 'LOGIN'
  | 'LOGOUT'
  | 'LOGIN_FAILED'
  | 'SESSION_START'
  | 'SESSION_END'
  | 'ADMIN_USER_CREATE'
  | 'ADMIN_USER_UPDATE'
  | 'ADMIN_USER_DELETE'
  | 'ADMIN_PROMPT_UPDATE'
  | 'ERROR';

interface AuditEvent {
  timestamp: string;
  action: AuditAction;
  userId?: string;
  email?: string;
  details?: Record<string, unknown>;
}

/**
 * Log an audit event
 * Outputs structured JSON for App Insights ingestion
 */
export function audit(
  action: AuditAction,
  options?: {
    userId?: string;
    email?: string;
    details?: Record<string, unknown>;
  }
): void {
  const event: AuditEvent = {
    timestamp: new Date().toISOString(),
    action,
    ...options,
  };

  // Structured log for App Insights
  console.log('AUDIT:', JSON.stringify(event));
}

// Convenience functions
export const auditLog = {
  login: (email: string, userId?: string) =>
    audit('LOGIN', { email, userId }),

  loginFailed: (email: string, reason?: string) =>
    audit('LOGIN_FAILED', { email, details: { reason } }),

  logout: (email: string) =>
    audit('LOGOUT', { email }),

  sessionStart: (userId: string, sessionId: string) =>
    audit('SESSION_START', { userId, details: { sessionId } }),

  sessionEnd: (userId: string, sessionId: string) =>
    audit('SESSION_END', { userId, details: { sessionId } }),

  adminAction: (action: 'ADMIN_USER_CREATE' | 'ADMIN_USER_UPDATE' | 'ADMIN_USER_DELETE' | 'ADMIN_PROMPT_UPDATE',
                userId: string,
                targetId: string) =>
    audit(action, { userId, details: { targetId } }),

  error: (context: string, error: unknown) =>
    audit('ERROR', { details: { context, error: String(error) } }),
};
```

#### Usage

```typescript
import { auditLog } from "@/lib/audit";

// In auth callback
auditLog.login(user.email, user.id);

// In admin routes
auditLog.adminAction('ADMIN_USER_UPDATE', session.user.id, targetUserId);

// In error handlers
auditLog.error('api/chat', error);
```

---

## Deployment Checklist

### 1. Create New Files

```
ui/lib/cors.ts
ui/lib/validation.ts
ui/lib/rate-limiter.ts
ui/lib/errors.ts
ui/lib/audit.ts
orchestrator/shared_code/prompt_monitor.py
orchestrator/shared_code/auth.py
```

### 2. Update Existing Files

- Update API routes with CORS, validation, rate limiting
- Update `next.config.mjs` with security headers
- Update `.gitignore`
- Update Function App endpoints with auth decorator

### 3. Configure Secrets

```bash
SECRET=$(openssl rand -base64 32)
az webapp config appsettings set -g rg-PULSE-training-prod -n app-PULSE-training-ui-prod \
  --settings FUNCTION_APP_SHARED_SECRET="$SECRET"
az functionapp config appsettings set -g rg-PULSE-training-prod -n func-PULSE-training-orchestrator-prod \
  --settings FUNCTION_APP_SHARED_SECRET="$SECRET"
```

### 4. Deploy and Test

```bash
# Build and deploy UI
cd ui && npm run build
# Deploy...

# Deploy Function App
cd orchestrator
# Deploy...

# Verify app works normally
# Check rate limits don't trigger during normal use
# Verify CORS allows the app to function
```

---

## What We're NOT Doing (And Why)

| Omitted | Reason |
|---------|--------|
| Blocking prompt injections | Azure OpenAI has content filters; AI handles weird input naturally |
| Complex input sanitization | No database writes from user input; AI doesn't execute code |
| Aggressive rate limits | Normal usage should never hit limits |
| Session check on every request | Performance impact; only needed for admin actions |
| Strict CSP | Would break legitimate functionality |
| Complex CORS validation | Simple allowlist is sufficient |

---

## Summary

This minimal approach:
- **Protects against real risks** (cost explosion, unauthorized access)
- **Won't break the demo** (generous limits, permissive policies)
- **Monitors rather than blocks** AI interactions
- **Can be implemented quickly** (~12 hours)
- **Leaves room for post-hackathon hardening**

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2024-12-25 | Development | Initial comprehensive plan |
| 1.1 | 2024-12-25 | Development | Revised to minimal effective controls; removed overcompensating restrictions; changed prompt protection to monitor-only |

---

**Classification:** INTERNAL
**Next Review:** Post-hackathon (January 2026)
