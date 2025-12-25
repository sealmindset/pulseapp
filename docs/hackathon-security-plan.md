# PULSE Hackathon Security Implementation Plan

> **Target Date:** January 7, 2026 Hackathon Demo
> **Role Constraints:** Azure Contributor (no Global Admin, Network, or Identity team dependencies)
> **Objective:** Implement maximum security hardening with application-level changes only

---

## Constraint Analysis

### What You CAN Do (Contributor Role)

| Action | Possible | Notes |
|--------|----------|-------|
| Modify application code (UI/Orchestrator) | Yes | Full control |
| Update App Settings on existing Web App | Yes | Contributors can modify |
| Update App Settings on existing Function App | Yes | Contributors can modify |
| Deploy code changes | Yes | Via zip deploy |
| Modify `.gitignore` | Yes | Local repo control |
| Rotate secrets in existing Azure AD app | **Maybe** | May need App Registration Owner |
| Create Azure Key Vault | **No** | Requires Owner or elevated role |
| Create NSGs | **No** | Network team typically owns |
| Create WAF/Front Door | **No** | New resource creation |
| Disable public network access | **No** | Requires Network/DNS team |
| Modify PostgreSQL auth method | **No** | Database admin required |

### What Requires Other Teams

| Security Gap | Blocked By |
|--------------|------------|
| Public Network Access = false | Network team (DNS forwarding required) |
| NSG deployment | Network team |
| WAF deployment | Network/Security team |
| Azure Key Vault creation | Owner/Global Admin |
| Managed Identity for PostgreSQL | Database/Identity team |
| Secret rotation (Azure AD) | Identity/App Registration Owner |

---

## Implementable Security Fixes (Application-Level)

The following can be implemented **immediately** with code changes only:

### Phase 1: Critical - Code Changes (No Azure Portal Access Needed)

#### 1. CORS Hardening (2 hours)
**Risk Addressed:** CORS wildcard allows any origin to access APIs
**Impact:** Eliminates cross-origin attack vector

**Files to modify:**
- `ui/lib/cors.ts` (new)
- `ui/app/api/orchestrator/chat/route.ts`
- `ui/app/api/orchestrator/context/route.ts`
- `ui/app/api/orchestrator/admin/prompts/route.ts`
- All other API routes with `Access-Control-Allow-Origin: *`
- `orchestrator/chat/__init__.py`

**Implementation:**

```typescript
// ui/lib/cors.ts
const ALLOWED_ORIGINS = [
  process.env.NEXT_PUBLIC_APP_URL,
  'https://app-pulse-training-ui-prod.azurewebsites.net',
].filter(Boolean);

export function getCorsHeaders(origin: string | null): HeadersInit {
  const allowedOrigin = origin && ALLOWED_ORIGINS.includes(origin)
    ? origin
    : ALLOWED_ORIGINS[0] || '';

  return {
    'Access-Control-Allow-Origin': allowedOrigin,
    'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    'Access-Control-Allow-Credentials': 'true',
  };
}
```

**Deployment:** Code change only - redeploy UI

---

#### 2. Prompt Injection Protection (4 hours)
**Risk Addressed:** User input directly interpolated into AI prompts
**Impact:** Prevents prompt manipulation, system prompt extraction

**Files to modify:**
- `ui/lib/prompt-security.ts` (new)
- `orchestrator/shared_code/openai_client.py`
- `orchestrator/chat/__init__.py`

**Implementation:**

```typescript
// ui/lib/prompt-security.ts
const INJECTION_PATTERNS = [
  /ignore (all )?(previous|prior|above)/i,
  /disregard (all )?(previous|prior|above)/i,
  /forget (all )?(previous|prior|above)/i,
  /system prompt/i,
  /you are now/i,
  /new instructions/i,
  /override/i,
  /jailbreak/i,
  /DAN mode/i,
  /\[INST\]/i,
  /\[\/INST\]/i,
  /<\|.*\|>/,  // Special tokens
];

export function detectPromptInjection(input: string): {
  safe: boolean;
  risk: 'low' | 'medium' | 'high';
  matches: string[];
} {
  const matches: string[] = [];

  for (const pattern of INJECTION_PATTERNS) {
    if (pattern.test(input)) {
      matches.push(pattern.source);
    }
  }

  if (matches.length >= 3) return { safe: false, risk: 'high', matches };
  if (matches.length >= 1) return { safe: false, risk: 'medium', matches };
  return { safe: true, risk: 'low', matches: [] };
}

export function sanitizeUserInput(input: string): string {
  // Remove common injection delimiters
  let sanitized = input
    .replace(/```/g, '')
    .replace(/\[INST\]/gi, '')
    .replace(/\[\/INST\]/gi, '')
    .replace(/<\|[^|]*\|>/g, '')
    .replace(/#{3,}/g, '');

  // Limit length
  if (sanitized.length > 2000) {
    sanitized = sanitized.substring(0, 2000);
  }

  return sanitized.trim();
}
```

```python
# orchestrator/shared_code/prompt_security.py
import re
import logging

INJECTION_PATTERNS = [
    r'ignore (all )?(previous|prior|above)',
    r'disregard (all )?(previous|prior|above)',
    r'forget (all )?(previous|prior|above)',
    r'system prompt',
    r'you are now',
    r'new instructions',
    r'override',
    r'jailbreak',
    r'DAN mode',
    r'\[INST\]',
    r'\[/INST\]',
    r'<\|.*\|>',
]

def detect_injection(user_input: str) -> dict:
    """Detect potential prompt injection attempts."""
    matches = []
    input_lower = user_input.lower()

    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, input_lower, re.IGNORECASE):
            matches.append(pattern)

    risk = 'high' if len(matches) >= 3 else 'medium' if matches else 'low'

    if matches:
        logging.warning(f"Prompt injection detected: risk={risk}, patterns={matches}")

    return {
        'safe': len(matches) == 0,
        'risk': risk,
        'matches': matches
    }

def sanitize_input(user_input: str, max_length: int = 2000) -> str:
    """Sanitize user input to remove injection vectors."""
    sanitized = user_input
    sanitized = re.sub(r'```', '', sanitized)
    sanitized = re.sub(r'\[INST\]', '', sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r'\[/INST\]', '', sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r'<\|[^|]*\|>', '', sanitized)
    sanitized = re.sub(r'#{3,}', '', sanitized)

    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]

    return sanitized.strip()
```

**Deployment:** Code change only - redeploy UI and Function App

---

#### 3. Input Validation (3 hours)
**Risk Addressed:** Admin routes lack input sanitization
**Impact:** Prevents XSS, SQL injection, path traversal

**Files to modify:**
- `ui/lib/validation.ts` (new)
- All API route handlers

**Implementation:**

```typescript
// ui/lib/validation.ts
import { z } from 'zod';

// Session ID validation
export const sessionIdSchema = z.string().uuid();

// Message validation
export const messageSchema = z.string()
  .min(1, 'Message cannot be empty')
  .max(2000, 'Message too long')
  .refine(
    (val) => !/<script/i.test(val),
    'Invalid content detected'
  );

// User input sanitizer
export function sanitizeHtml(input: string): string {
  return input
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

// Security checks
export function containsSqlInjection(input: string): boolean {
  const patterns = [
    /(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|ALTER)\b)/i,
    /('|"|;|--)/,
    /(\bOR\b|\bAND\b).*=/i,
  ];
  return patterns.some(p => p.test(input));
}

export function containsPathTraversal(input: string): boolean {
  return /\.\.\/|\.\.\\/.test(input);
}
```

**Deployment:** Code change only - redeploy UI

---

#### 4. Rate Limiting (Application-Level) (4 hours)
**Risk Addressed:** No rate limiting on API routes
**Impact:** Prevents DoS, cost explosion, brute force

**Files to modify:**
- `ui/lib/rate-limiter.ts` (new)
- `ui/middleware.ts`
- API route handlers

**Implementation:**

```typescript
// ui/lib/rate-limiter.ts
interface RateLimitEntry {
  count: number;
  resetTime: number;
}

// In-memory store (works for single instance, use Redis for scaled deployment)
const rateLimitStore = new Map<string, RateLimitEntry>();

interface RateLimitConfig {
  windowMs: number;  // Time window in milliseconds
  maxRequests: number;  // Max requests per window
}

const RATE_LIMITS: Record<string, RateLimitConfig> = {
  'api/orchestrator/chat': { windowMs: 60000, maxRequests: 30 },
  'api/orchestrator/context': { windowMs: 60000, maxRequests: 10 },
  'api/auth': { windowMs: 60000, maxRequests: 10 },
  'default': { windowMs: 60000, maxRequests: 100 },
};

export function checkRateLimit(
  identifier: string,  // IP or user ID
  endpoint: string
): { allowed: boolean; remaining: number; resetIn: number } {
  const config = RATE_LIMITS[endpoint] || RATE_LIMITS['default'];
  const key = `${identifier}:${endpoint}`;
  const now = Date.now();

  let entry = rateLimitStore.get(key);

  // Clean up expired entries periodically
  if (!entry || now > entry.resetTime) {
    entry = { count: 0, resetTime: now + config.windowMs };
    rateLimitStore.set(key, entry);
  }

  entry.count++;

  const allowed = entry.count <= config.maxRequests;
  const remaining = Math.max(0, config.maxRequests - entry.count);
  const resetIn = Math.max(0, entry.resetTime - now);

  return { allowed, remaining, resetIn };
}

export function getRateLimitHeaders(
  remaining: number,
  resetIn: number,
  limit: number
): HeadersInit {
  return {
    'X-RateLimit-Limit': limit.toString(),
    'X-RateLimit-Remaining': remaining.toString(),
    'X-RateLimit-Reset': Math.ceil(resetIn / 1000).toString(),
  };
}
```

**Usage in API routes:**

```typescript
// In any API route
import { checkRateLimit, getRateLimitHeaders } from '@/lib/rate-limiter';

export async function POST(req: NextRequest) {
  const ip = req.headers.get('x-forwarded-for') || 'unknown';
  const { allowed, remaining, resetIn } = checkRateLimit(ip, 'api/orchestrator/chat');

  if (!allowed) {
    return new Response(JSON.stringify({ error: 'Too many requests' }), {
      status: 429,
      headers: {
        'Content-Type': 'application/json',
        'Retry-After': Math.ceil(resetIn / 1000).toString(),
        ...getRateLimitHeaders(remaining, resetIn, 30),
      },
    });
  }

  // ... rest of handler
}
```

**Deployment:** Code change only - redeploy UI

---

#### 5. Session Security Enhancements (2 hours)
**Risk Addressed:** No session revocation, disabled users retain access
**Impact:** Immediate access termination for disabled users

**Files to modify:**
- `ui/lib/auth-config.ts`
- `ui/app/api/auth/[...nextauth]/route.ts`

**Implementation:**

```typescript
// Add to auth-config.ts callbacks
callbacks: {
  async jwt({ token, user, trigger }) {
    // On every request, verify user is still active
    if (trigger === 'update' || token.sub) {
      const dbUser = await getUserById(token.sub);
      if (!dbUser || dbUser.status !== 'active') {
        // Force logout by returning empty token
        return {};
      }
      // Refresh role in case it changed
      token.role = dbUser.role;
    }
    return token;
  },

  async session({ session, token }) {
    // If token is empty (user disabled), session is invalid
    if (!token.sub) {
      return null as any;
    }
    session.user.role = token.role as string;
    return session;
  },
}
```

**Deployment:** Code change only - redeploy UI

---

#### 6. Security Headers (1 hour)
**Risk Addressed:** Missing security headers
**Impact:** Defense-in-depth against XSS, clickjacking

**Files to modify:**
- `ui/next.config.js`

**Implementation:**

```javascript
// next.config.js
const securityHeaders = [
  {
    key: 'X-DNS-Prefetch-Control',
    value: 'on'
  },
  {
    key: 'Strict-Transport-Security',
    value: 'max-age=63072000; includeSubDomains; preload'
  },
  {
    key: 'X-Frame-Options',
    value: 'SAMEORIGIN'
  },
  {
    key: 'X-Content-Type-Options',
    value: 'nosniff'
  },
  {
    key: 'Referrer-Policy',
    value: 'strict-origin-when-cross-origin'
  },
  {
    key: 'Permissions-Policy',
    value: 'camera=(), microphone=(self), geolocation=()'
  },
  {
    key: 'Content-Security-Policy',
    value: [
      "default-src 'self'",
      "script-src 'self' 'unsafe-inline' 'unsafe-eval'",  // Next.js requires these
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' data: https:",
      "font-src 'self' data:",
      "connect-src 'self' https://*.azure.com https://*.microsoft.com",
      "frame-ancestors 'self'",
    ].join('; ')
  }
];

module.exports = {
  async headers() {
    return [
      {
        source: '/:path*',
        headers: securityHeaders,
      },
    ];
  },
  // ... rest of config
};
```

**Deployment:** Code change only - redeploy UI

---

#### 7. Git Hygiene (30 minutes)
**Risk Addressed:** Secrets in git history, tfvars tracked
**Impact:** Prevents future credential exposure

**Files to modify:**
- `.gitignore`

**Add to .gitignore:**

```gitignore
# Terraform
*.tfvars
*.tfvars.json
*.tfstate
*.tfstate.*
.terraform/
tfplan*
crash.log

# Secrets
.env
.env.*
!.env.example
*.pem
*.key
credentials.json

# IDE
.idea/
.vscode/
*.swp
*.swo
```

**Note:** This prevents future exposure. Historical secrets should be rotated (requires Identity team).

---

### Phase 2: Medium Priority - Enhanced Protection

#### 8. API Authentication for Function App (2 hours)
**Current State:** Function App accepts requests without authentication
**Mitigation:** Add shared secret validation between UI and Function App

**Files to modify:**
- `ui/app/api/orchestrator/chat/route.ts` (and other proxy routes)
- `orchestrator/chat/__init__.py` (and other endpoints)

**Implementation:**

```typescript
// UI side - add to all Function App proxy calls
const FUNCTION_APP_SECRET = process.env.FUNCTION_APP_SHARED_SECRET;

const res = await fetch(target, {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "X-Function-Key": FUNCTION_APP_SECRET || '',
  },
  body: JSON.stringify(json),
});
```

```python
# Function App side - add to all endpoints
import os

def validate_request(req: func.HttpRequest) -> bool:
    """Validate request has correct shared secret."""
    expected = os.environ.get('SHARED_SECRET')
    if not expected:
        return True  # Skip validation if not configured

    provided = req.headers.get('X-Function-Key', '')
    return provided == expected
```

**Deployment:**
1. Generate secret: `openssl rand -base64 32`
2. Add `FUNCTION_APP_SHARED_SECRET` to UI App Settings
3. Add `SHARED_SECRET` to Function App App Settings
4. Deploy code changes

---

#### 9. Error Message Sanitization (1 hour)
**Risk Addressed:** Error messages may leak internal details
**Impact:** Prevents information disclosure

**Files to modify:**
- All API route handlers
- `orchestrator/**/__init__.py`

**Implementation:**

```typescript
// ui/lib/errors.ts
export function safeErrorMessage(error: unknown): string {
  // Never expose internal error details
  if (error instanceof Error) {
    // Log full error internally
    console.error('Internal error:', error);

    // Return generic message to client
    if (error.message.includes('ECONNREFUSED')) {
      return 'Service temporarily unavailable';
    }
    if (error.message.includes('timeout')) {
      return 'Request timed out';
    }
  }
  return 'An unexpected error occurred';
}
```

---

#### 10. Audit Logging Enhancement (2 hours)
**Risk Addressed:** Incomplete audit logging
**Impact:** Better forensics and compliance

**Files to modify:**
- `ui/lib/audit-logger.ts` (new)
- API route handlers

**Implementation:**

```typescript
// ui/lib/audit-logger.ts
import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth-config';

interface AuditEvent {
  timestamp: string;
  action: string;
  userId: string | null;
  userEmail: string | null;
  resource: string;
  resourceId?: string;
  ipAddress: string;
  userAgent: string;
  success: boolean;
  details?: Record<string, unknown>;
}

export async function logAuditEvent(
  req: Request,
  action: string,
  resource: string,
  success: boolean,
  details?: Record<string, unknown>
): Promise<void> {
  const session = await getServerSession(authOptions);

  const event: AuditEvent = {
    timestamp: new Date().toISOString(),
    action,
    userId: session?.user?.id || null,
    userEmail: session?.user?.email || null,
    resource,
    ipAddress: req.headers.get('x-forwarded-for') || 'unknown',
    userAgent: req.headers.get('user-agent') || 'unknown',
    success,
    details,
  };

  // Log to console (picked up by App Insights)
  console.log('AUDIT:', JSON.stringify(event));
}
```

---

## Implementation Summary

### Immediately Implementable (Code-Only)

| Fix | Effort | Risk Addressed | Priority |
|-----|--------|----------------|----------|
| CORS Hardening | 2h | Cross-origin attacks | Critical |
| Prompt Injection Protection | 4h | AI manipulation | Critical |
| Input Validation | 3h | XSS, injection | Critical |
| Rate Limiting | 4h | DoS, cost explosion | High |
| Session Security | 2h | Unauthorized access | High |
| Security Headers | 1h | XSS, clickjacking | Medium |
| Git Hygiene | 0.5h | Credential exposure | Medium |
| Function App Auth | 2h | Unauthorized API access | Medium |
| Error Sanitization | 1h | Information disclosure | Medium |
| Audit Logging | 2h | Compliance, forensics | Medium |

**Total Effort:** ~21 hours

### Blocked Items (Require Other Teams)

| Fix | Blocked By | Risk Level |
|-----|------------|------------|
| Public Network Access = false | Network team (DNS) | Critical |
| Azure Key Vault | Owner/Global Admin | Critical |
| NSG Deployment | Network team | High |
| WAF Deployment | Network team | High |
| Managed Identity for PostgreSQL | Database/Identity | High |
| Secret Rotation | Identity team | High |

---

## Recommended Implementation Order

### Before Hackathon (January 7, 2026)

1. **Day 1:** CORS Hardening + Security Headers (3 hours)
2. **Day 1:** Input Validation (3 hours)
3. **Day 2:** Prompt Injection Protection (4 hours)
4. **Day 2:** Rate Limiting (4 hours)
5. **Day 3:** Session Security + Git Hygiene (2.5 hours)
6. **Day 3:** Function App Auth + Error Sanitization (3 hours)
7. **Day 4:** Testing and validation (4 hours)

### Post-Hackathon (Coordinate with Teams)

1. Submit request to Network team for DNS forwarding
2. Request Key Vault creation from Global Admin
3. Coordinate with Identity team for secret rotation
4. Plan WAF/NSG deployment with Security team

---

## Testing Checklist

Before deploying to production:

- [ ] CORS: Test that non-allowed origins are rejected
- [ ] Prompt Injection: Test common injection patterns are blocked
- [ ] Input Validation: Test XSS/SQL injection payloads are rejected
- [ ] Rate Limiting: Test that rate limits trigger after threshold
- [ ] Session: Test that disabled user's session is terminated
- [ ] Headers: Verify security headers in browser dev tools
- [ ] Function App Auth: Test that requests without secret are rejected
- [ ] Audit Logs: Verify events appear in App Insights

---

## Risk Acknowledgment

The following risks remain until cross-functional work is completed:

| Risk | Severity | Mitigation Status |
|------|----------|-------------------|
| Public network access | Critical | **Cannot be mitigated without Network team** |
| No Key Vault | Critical | **Cannot be mitigated without Global Admin** |
| Secrets in git history | High | Git hygiene prevents new exposure; rotation requires Identity team |
| No NSG/WAF | High | Application-level controls provide partial coverage |

**Recommendation:** After the hackathon, prioritize coordination with Network and Identity teams to address the blocked items.
