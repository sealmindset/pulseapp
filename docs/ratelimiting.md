# PULSE Rate Limiting Implementation Guide

**Version:** 1.0
**Last Updated:** 2025-12-25
**Priority:** HIGH
**Related Documents:** [securedbydesign.md](securedbydesign.md), [promptsecurity.md](promptsecurity.md), [wafconfig.md](wafconfig.md)

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Why Rate Limiting Matters](#why-rate-limiting-matters)
3. [Rate Limiting Architecture](#rate-limiting-architecture)
4. [Application-Level Rate Limiting](#application-level-rate-limiting)
5. [Azure API Management Rate Limiting](#azure-api-management-rate-limiting)
6. [Azure Front Door Rate Limiting](#azure-front-door-rate-limiting)
7. [Function App Rate Limiting](#function-app-rate-limiting)
8. [Redis-Based Distributed Rate Limiting](#redis-based-distributed-rate-limiting)
9. [AI/LLM Specific Rate Limiting](#aillm-specific-rate-limiting)
10. [Monitoring and Alerting](#monitoring-and-alerting)
11. [Testing and Validation](#testing-and-validation)
12. [Migration Checklist](#migration-checklist)

---

## Executive Summary

Rate limiting is essential to protect the PULSE application from:

- **Denial of Service (DoS)** attacks
- **Cost overruns** from excessive API usage
- **Resource exhaustion** in backend services
- **API abuse** and data scraping
- **Azure OpenAI quota exhaustion**

This guide provides comprehensive implementation patterns for multi-layer rate limiting across the PULSE infrastructure.

---

## Why Rate Limiting Matters

### Threat Scenarios

| Threat | Impact | Rate Limiting Defense |
|--------|--------|----------------------|
| DoS Attack | Service unavailability | Block excessive requests per IP |
| API Abuse | Data scraping, unauthorized automation | Limit requests per user/API key |
| Cost Attack | Azure bill spike (especially OpenAI) | Token/request quotas |
| Resource Exhaustion | Backend overload | Queue-based throttling |
| Account Takeover | Brute force attacks | Auth endpoint protection |

### Cost Protection

Azure OpenAI pricing makes rate limiting critical:
- GPT-4: ~$0.03-0.06 per 1K tokens
- Without limits, a single malicious actor could generate thousands of dollars in charges

---

## Rate Limiting Architecture

### Multi-Layer Defense

```
┌─────────────────────────────────────────────────────────────────┐
│                     Layer 1: Azure Front Door                    │
│              (DDoS protection, IP-based rate limiting)           │
├─────────────────────────────────────────────────────────────────┤
│                   Layer 2: Web Application Firewall              │
│               (Bot detection, geo-blocking, rule-based)          │
├─────────────────────────────────────────────────────────────────┤
│                   Layer 3: Azure API Management                  │
│            (API key quotas, subscription rate limits)            │
├─────────────────────────────────────────────────────────────────┤
│                    Layer 4: Application Layer                    │
│         (Per-user limits, sliding windows, Redis-backed)         │
├─────────────────────────────────────────────────────────────────┤
│                    Layer 5: Service-Specific                     │
│        (Azure OpenAI TPM/RPM limits, storage throttling)         │
└─────────────────────────────────────────────────────────────────┘
```

### Recommended Limits

| Endpoint | Limit Type | Recommended Value | Rationale |
|----------|------------|-------------------|-----------|
| `/api/chat` | Per user/minute | 20 requests | Prevent OpenAI abuse |
| `/api/chat` | Per user/day | 500 requests | Cost control |
| `/api/auth/*` | Per IP/minute | 10 requests | Prevent brute force |
| `/api/*` (general) | Per IP/minute | 100 requests | General DoS protection |
| Static assets | Per IP/minute | 500 requests | CDN should handle |
| WebSocket | Per user/hour | 100 connections | Connection limit |

---

## Application-Level Rate Limiting

### Create Rate Limiter Module

Create `ui/lib/rate-limiter.ts`:

```typescript
/**
 * PULSE Rate Limiter
 * Application-level rate limiting with multiple strategies
 */

export interface RateLimitConfig {
  /** Maximum requests allowed in the window */
  maxRequests: number;
  /** Window size in milliseconds */
  windowMs: number;
  /** Key prefix for storage */
  keyPrefix?: string;
  /** Skip rate limiting for certain conditions */
  skip?: (identifier: string) => boolean;
  /** Custom message when rate limited */
  message?: string;
}

export interface RateLimitResult {
  allowed: boolean;
  remaining: number;
  resetTime: number;
  retryAfter?: number;
}

export interface RateLimitStore {
  increment(key: string, windowMs: number): Promise<{ count: number; resetTime: number }>;
  get(key: string): Promise<{ count: number; resetTime: number } | null>;
  reset(key: string): Promise<void>;
}

/**
 * In-memory rate limit store (for single instance deployments)
 * Use Redis store for production multi-instance deployments
 */
export class MemoryRateLimitStore implements RateLimitStore {
  private store: Map<string, { count: number; resetTime: number }> = new Map();
  private cleanupInterval: NodeJS.Timeout;

  constructor() {
    // Cleanup expired entries every minute
    this.cleanupInterval = setInterval(() => this.cleanup(), 60000);
  }

  async increment(key: string, windowMs: number): Promise<{ count: number; resetTime: number }> {
    const now = Date.now();
    const existing = this.store.get(key);

    if (existing && now < existing.resetTime) {
      existing.count++;
      return existing;
    }

    const newEntry = {
      count: 1,
      resetTime: now + windowMs,
    };
    this.store.set(key, newEntry);
    return newEntry;
  }

  async get(key: string): Promise<{ count: number; resetTime: number } | null> {
    const entry = this.store.get(key);
    if (!entry || Date.now() >= entry.resetTime) {
      return null;
    }
    return entry;
  }

  async reset(key: string): Promise<void> {
    this.store.delete(key);
  }

  private cleanup(): void {
    const now = Date.now();
    for (const [key, entry] of this.store.entries()) {
      if (now >= entry.resetTime) {
        this.store.delete(key);
      }
    }
  }

  destroy(): void {
    clearInterval(this.cleanupInterval);
  }
}

/**
 * Fixed Window Rate Limiter
 * Simple, efficient, but can allow 2x burst at window boundaries
 */
export class FixedWindowRateLimiter {
  private store: RateLimitStore;
  private config: Required<RateLimitConfig>;

  constructor(config: RateLimitConfig, store?: RateLimitStore) {
    this.store = store || new MemoryRateLimitStore();
    this.config = {
      maxRequests: config.maxRequests,
      windowMs: config.windowMs,
      keyPrefix: config.keyPrefix || 'rl',
      skip: config.skip || (() => false),
      message: config.message || 'Too many requests. Please try again later.',
    };
  }

  async check(identifier: string): Promise<RateLimitResult> {
    if (this.config.skip(identifier)) {
      return { allowed: true, remaining: this.config.maxRequests, resetTime: 0 };
    }

    const key = `${this.config.keyPrefix}:${identifier}`;
    const { count, resetTime } = await this.store.increment(key, this.config.windowMs);

    const allowed = count <= this.config.maxRequests;
    const remaining = Math.max(0, this.config.maxRequests - count);
    const retryAfter = allowed ? undefined : Math.ceil((resetTime - Date.now()) / 1000);

    return { allowed, remaining, resetTime, retryAfter };
  }

  get message(): string {
    return this.config.message;
  }
}

/**
 * Sliding Window Rate Limiter
 * More accurate than fixed window, prevents boundary burst
 */
export class SlidingWindowRateLimiter {
  private store: RateLimitStore;
  private config: Required<RateLimitConfig>;
  private timestamps: Map<string, number[]> = new Map();

  constructor(config: RateLimitConfig, store?: RateLimitStore) {
    this.store = store || new MemoryRateLimitStore();
    this.config = {
      maxRequests: config.maxRequests,
      windowMs: config.windowMs,
      keyPrefix: config.keyPrefix || 'srl',
      skip: config.skip || (() => false),
      message: config.message || 'Rate limit exceeded. Please wait before retrying.',
    };
  }

  async check(identifier: string): Promise<RateLimitResult> {
    if (this.config.skip(identifier)) {
      return { allowed: true, remaining: this.config.maxRequests, resetTime: 0 };
    }

    const now = Date.now();
    const windowStart = now - this.config.windowMs;
    const key = `${this.config.keyPrefix}:${identifier}`;

    // Get existing timestamps
    let timestamps = this.timestamps.get(key) || [];

    // Filter out expired timestamps
    timestamps = timestamps.filter(ts => ts > windowStart);

    // Check if allowed
    const allowed = timestamps.length < this.config.maxRequests;

    if (allowed) {
      timestamps.push(now);
      this.timestamps.set(key, timestamps);
    }

    const remaining = Math.max(0, this.config.maxRequests - timestamps.length);
    const oldestTimestamp = timestamps[0] || now;
    const resetTime = oldestTimestamp + this.config.windowMs;
    const retryAfter = allowed ? undefined : Math.ceil((resetTime - now) / 1000);

    return { allowed, remaining, resetTime, retryAfter };
  }

  get message(): string {
    return this.config.message;
  }
}

/**
 * Token Bucket Rate Limiter
 * Allows bursts while enforcing average rate
 */
export class TokenBucketRateLimiter {
  private buckets: Map<string, { tokens: number; lastRefill: number }> = new Map();
  private maxTokens: number;
  private refillRate: number; // tokens per millisecond
  private keyPrefix: string;
  private skipFn: (identifier: string) => boolean;
  private customMessage: string;

  constructor(config: {
    maxTokens: number;
    refillRatePerSecond: number;
    keyPrefix?: string;
    skip?: (identifier: string) => boolean;
    message?: string;
  }) {
    this.maxTokens = config.maxTokens;
    this.refillRate = config.refillRatePerSecond / 1000;
    this.keyPrefix = config.keyPrefix || 'tb';
    this.skipFn = config.skip || (() => false);
    this.customMessage = config.message || 'Rate limit exceeded.';
  }

  async check(identifier: string, tokensRequired: number = 1): Promise<RateLimitResult> {
    if (this.skipFn(identifier)) {
      return { allowed: true, remaining: this.maxTokens, resetTime: 0 };
    }

    const now = Date.now();
    const key = `${this.keyPrefix}:${identifier}`;

    let bucket = this.buckets.get(key);

    if (!bucket) {
      bucket = { tokens: this.maxTokens, lastRefill: now };
    } else {
      // Refill tokens based on time elapsed
      const elapsed = now - bucket.lastRefill;
      const tokensToAdd = elapsed * this.refillRate;
      bucket.tokens = Math.min(this.maxTokens, bucket.tokens + tokensToAdd);
      bucket.lastRefill = now;
    }

    const allowed = bucket.tokens >= tokensRequired;

    if (allowed) {
      bucket.tokens -= tokensRequired;
    }

    this.buckets.set(key, bucket);

    const remaining = Math.floor(bucket.tokens);
    const timeToRefill = Math.ceil((tokensRequired - bucket.tokens) / this.refillRate);
    const resetTime = now + (this.maxTokens - bucket.tokens) / this.refillRate;
    const retryAfter = allowed ? undefined : Math.ceil(timeToRefill / 1000);

    return { allowed, remaining, resetTime, retryAfter };
  }

  get message(): string {
    return this.customMessage;
  }
}

/**
 * Composite Rate Limiter
 * Combines multiple rate limiters (all must pass)
 */
export class CompositeRateLimiter {
  private limiters: { name: string; limiter: FixedWindowRateLimiter | SlidingWindowRateLimiter | TokenBucketRateLimiter }[];

  constructor(limiters: { name: string; limiter: FixedWindowRateLimiter | SlidingWindowRateLimiter | TokenBucketRateLimiter }[]) {
    this.limiters = limiters;
  }

  async check(identifier: string, tokensRequired?: number): Promise<RateLimitResult & { failedLimiter?: string }> {
    for (const { name, limiter } of this.limiters) {
      const result = await limiter.check(identifier, tokensRequired);
      if (!result.allowed) {
        return { ...result, failedLimiter: name };
      }
    }

    // All passed - return the most restrictive remaining
    const results = await Promise.all(
      this.limiters.map(({ limiter }) => limiter.check(identifier, tokensRequired))
    );

    return {
      allowed: true,
      remaining: Math.min(...results.map(r => r.remaining)),
      resetTime: Math.max(...results.map(r => r.resetTime)),
    };
  }
}
```

### Create Rate Limit Middleware

Create `ui/lib/rate-limit-middleware.ts`:

```typescript
/**
 * PULSE Rate Limit Middleware
 * Next.js API route rate limiting
 */

import { NextRequest, NextResponse } from 'next/server';
import {
  FixedWindowRateLimiter,
  SlidingWindowRateLimiter,
  TokenBucketRateLimiter,
  CompositeRateLimiter,
  RateLimitResult,
} from './rate-limiter';
import { logSecurityEvent } from './security-logger';

// Rate limiter instances (singleton)
let chatRateLimiter: CompositeRateLimiter | null = null;
let authRateLimiter: SlidingWindowRateLimiter | null = null;
let generalRateLimiter: FixedWindowRateLimiter | null = null;

/**
 * Initialize rate limiters
 */
function initializeLimiters() {
  if (!chatRateLimiter) {
    // Chat endpoint: composite limiter with multiple constraints
    chatRateLimiter = new CompositeRateLimiter([
      {
        name: 'per-minute',
        limiter: new SlidingWindowRateLimiter({
          maxRequests: 20,
          windowMs: 60 * 1000, // 1 minute
          message: 'You have exceeded the chat rate limit. Please wait a moment.',
        }),
      },
      {
        name: 'per-hour',
        limiter: new FixedWindowRateLimiter({
          maxRequests: 100,
          windowMs: 60 * 60 * 1000, // 1 hour
          message: 'Hourly chat limit reached. Please try again later.',
        }),
      },
      {
        name: 'per-day',
        limiter: new FixedWindowRateLimiter({
          maxRequests: 500,
          windowMs: 24 * 60 * 60 * 1000, // 24 hours
          message: 'Daily chat limit reached. Limit resets at midnight.',
        }),
      },
    ]);
  }

  if (!authRateLimiter) {
    // Auth endpoints: strict limiting to prevent brute force
    authRateLimiter = new SlidingWindowRateLimiter({
      maxRequests: 10,
      windowMs: 60 * 1000, // 1 minute
      message: 'Too many authentication attempts. Please wait before trying again.',
    });
  }

  if (!generalRateLimiter) {
    // General API: moderate limiting
    generalRateLimiter = new FixedWindowRateLimiter({
      maxRequests: 100,
      windowMs: 60 * 1000, // 1 minute
      message: 'Too many requests. Please slow down.',
    });
  }
}

/**
 * Extract client identifier for rate limiting
 */
export function getClientIdentifier(request: NextRequest): {
  userId?: string;
  ip: string;
  identifier: string;
} {
  // Try to get user ID from auth header or session
  const authHeader = request.headers.get('authorization');
  const userId = request.headers.get('x-user-id');

  // Get IP address
  const forwarded = request.headers.get('x-forwarded-for');
  const realIp = request.headers.get('x-real-ip');
  const ip = forwarded?.split(',')[0]?.trim() || realIp || request.ip || 'unknown';

  // Prefer user ID for authenticated requests, fall back to IP
  const identifier = userId || `ip:${ip}`;

  return { userId: userId || undefined, ip, identifier };
}

/**
 * Add rate limit headers to response
 */
function addRateLimitHeaders(response: NextResponse, result: RateLimitResult): NextResponse {
  response.headers.set('X-RateLimit-Remaining', result.remaining.toString());
  response.headers.set('X-RateLimit-Reset', result.resetTime.toString());

  if (result.retryAfter) {
    response.headers.set('Retry-After', result.retryAfter.toString());
  }

  return response;
}

/**
 * Create rate limit error response
 */
function createRateLimitResponse(result: RateLimitResult, message: string): NextResponse {
  const response = NextResponse.json(
    {
      error: message,
      retryAfter: result.retryAfter,
      code: 'RATE_LIMIT_EXCEEDED',
    },
    { status: 429 }
  );

  return addRateLimitHeaders(response, result);
}

/**
 * Rate limit middleware for chat endpoints
 */
export async function chatRateLimitMiddleware(
  request: NextRequest,
  handler: (request: NextRequest) => Promise<NextResponse>
): Promise<NextResponse> {
  initializeLimiters();

  const { identifier, ip, userId } = getClientIdentifier(request);
  const result = await chatRateLimiter!.check(identifier);

  if (!result.allowed) {
    await logSecurityEvent({
      type: 'RATE_LIMIT_EXCEEDED',
      clientId: identifier,
      path: request.nextUrl.pathname,
      timestamp: new Date().toISOString(),
      details: {
        ip,
        userId,
        limiter: (result as any).failedLimiter,
        retryAfter: result.retryAfter,
      },
    });

    const limiterMessage = (result as any).failedLimiter
      ? `Rate limit (${(result as any).failedLimiter}) exceeded.`
      : 'Rate limit exceeded.';

    return createRateLimitResponse(result, limiterMessage);
  }

  const response = await handler(request);
  return addRateLimitHeaders(response, result);
}

/**
 * Rate limit middleware for auth endpoints
 */
export async function authRateLimitMiddleware(
  request: NextRequest,
  handler: (request: NextRequest) => Promise<NextResponse>
): Promise<NextResponse> {
  initializeLimiters();

  // Always use IP for auth to prevent enumeration attacks
  const { ip } = getClientIdentifier(request);
  const identifier = `auth:${ip}`;
  const result = await authRateLimiter!.check(identifier);

  if (!result.allowed) {
    await logSecurityEvent({
      type: 'AUTH_RATE_LIMIT_EXCEEDED',
      clientId: identifier,
      path: request.nextUrl.pathname,
      timestamp: new Date().toISOString(),
      details: {
        ip,
        retryAfter: result.retryAfter,
      },
    });

    return createRateLimitResponse(result, authRateLimiter!.message);
  }

  const response = await handler(request);
  return addRateLimitHeaders(response, result);
}

/**
 * General rate limit middleware
 */
export async function generalRateLimitMiddleware(
  request: NextRequest,
  handler: (request: NextRequest) => Promise<NextResponse>
): Promise<NextResponse> {
  initializeLimiters();

  const { identifier, ip, userId } = getClientIdentifier(request);
  const result = await generalRateLimiter!.check(identifier);

  if (!result.allowed) {
    await logSecurityEvent({
      type: 'RATE_LIMIT_EXCEEDED',
      clientId: identifier,
      path: request.nextUrl.pathname,
      timestamp: new Date().toISOString(),
      details: { ip, userId },
    });

    return createRateLimitResponse(result, generalRateLimiter!.message);
  }

  const response = await handler(request);
  return addRateLimitHeaders(response, result);
}

/**
 * Higher-order function to wrap handlers with rate limiting
 */
export function withRateLimit(
  type: 'chat' | 'auth' | 'general',
  handler: (request: NextRequest) => Promise<NextResponse>
) {
  return async (request: NextRequest): Promise<NextResponse> => {
    switch (type) {
      case 'chat':
        return chatRateLimitMiddleware(request, handler);
      case 'auth':
        return authRateLimitMiddleware(request, handler);
      default:
        return generalRateLimitMiddleware(request, handler);
    }
  };
}
```

### Update API Routes

Update `ui/app/api/chat/route.ts`:

```typescript
import { NextRequest, NextResponse } from 'next/server';
import { withRateLimit } from '@/lib/rate-limit-middleware';
import { withPromptSecurity } from '@/lib/prompt-security-middleware';

async function handleChat(request: NextRequest, sanitizedBody?: any): Promise<NextResponse> {
  // Your existing chat logic here
  const body = sanitizedBody || await request.json();

  // ... process chat request ...

  return NextResponse.json({ message: 'Response' });
}

// Apply both rate limiting and prompt security
export const POST = withRateLimit('chat', withPromptSecurity(handleChat));
```

---

## Azure API Management Rate Limiting

### Terraform Configuration

Create `infra/modules/apim/rate-limiting.tf`:

```hcl
# API Management rate limiting policies

# Product-level rate limiting
resource "azurerm_api_management_product_policy" "pulse_product_policy" {
  product_id          = azurerm_api_management_product.pulse.product_id
  api_management_name = azurerm_api_management.pulse.name
  resource_group_name = var.resource_group_name

  xml_content = <<XML
<policies>
  <inbound>
    <!-- Rate limit by subscription key -->
    <rate-limit-by-key
      calls="1000"
      renewal-period="3600"
      counter-key="@(context.Subscription.Id)"
      increment-condition="@(context.Response.StatusCode >= 200 && context.Response.StatusCode < 400)" />

    <!-- Quota limit by subscription -->
    <quota-by-key
      calls="10000"
      bandwidth="10485760"
      renewal-period="86400"
      counter-key="@(context.Subscription.Id)" />

    <!-- IP-based rate limiting for unauthenticated requests -->
    <rate-limit-by-key
      calls="100"
      renewal-period="60"
      counter-key="@(context.Request.IpAddress)"
      increment-condition="@(context.Subscription == null)" />

    <base />
  </inbound>
  <backend>
    <base />
  </backend>
  <outbound>
    <!-- Add rate limit headers -->
    <set-header name="X-RateLimit-Limit" exists-action="override">
      <value>1000</value>
    </set-header>
    <base />
  </outbound>
  <on-error>
    <base />
  </on-error>
</policies>
XML
}

# API-level rate limiting for chat endpoint
resource "azurerm_api_management_api_policy" "chat_api_policy" {
  api_name            = azurerm_api_management_api.chat.name
  api_management_name = azurerm_api_management.pulse.name
  resource_group_name = var.resource_group_name

  xml_content = <<XML
<policies>
  <inbound>
    <!-- Stricter rate limit for chat API (Azure OpenAI cost control) -->
    <rate-limit-by-key
      calls="20"
      renewal-period="60"
      counter-key="@(context.Request.Headers.GetValueOrDefault("Authorization", context.Request.IpAddress))"
      retry-after-header-name="Retry-After"
      remaining-calls-header-name="X-RateLimit-Remaining" />

    <!-- Token-based quota for chat -->
    <quota-by-key
      calls="500"
      renewal-period="86400"
      counter-key="@(context.Request.Headers.GetValueOrDefault("Authorization", context.Request.IpAddress))" />

    <base />
  </inbound>
  <backend>
    <base />
  </backend>
  <outbound>
    <base />
  </outbound>
  <on-error>
    <!-- Custom error response for rate limiting -->
    <choose>
      <when condition="@(context.Response.StatusCode == 429)">
        <return-response>
          <set-status code="429" reason="Rate Limit Exceeded" />
          <set-header name="Content-Type" exists-action="override">
            <value>application/json</value>
          </set-header>
          <set-body>@{
            return new JObject(
              new JProperty("error", "Rate limit exceeded"),
              new JProperty("retryAfter", context.Response.Headers.GetValueOrDefault("Retry-After", "60")),
              new JProperty("code", "RATE_LIMIT_EXCEEDED")
            ).ToString();
          }</set-body>
        </return-response>
      </when>
    </choose>
    <base />
  </on-error>
</policies>
XML
}

# Named value for rate limit configuration (easily adjustable)
resource "azurerm_api_management_named_value" "rate_limit_chat_per_minute" {
  name                = "rate-limit-chat-per-minute"
  api_management_name = azurerm_api_management.pulse.name
  resource_group_name = var.resource_group_name
  display_name        = "Chat API Rate Limit (per minute)"
  value               = "20"
}

resource "azurerm_api_management_named_value" "rate_limit_chat_per_day" {
  name                = "rate-limit-chat-per-day"
  api_management_name = azurerm_api_management.pulse.name
  resource_group_name = var.resource_group_name
  display_name        = "Chat API Rate Limit (per day)"
  value               = "500"
}
```

---

## Azure Front Door Rate Limiting

### Terraform Configuration

Create `infra/modules/frontdoor/rate-limiting.tf`:

```hcl
# Azure Front Door WAF with rate limiting

resource "azurerm_cdn_frontdoor_firewall_policy" "pulse_waf" {
  name                = "pulsewafpolicy"
  resource_group_name = var.resource_group_name
  sku_name            = "Premium_AzureFrontDoor"
  mode                = "Prevention"
  enabled             = true

  # Rate limiting rule - General
  custom_rule {
    name     = "RateLimitGeneral"
    priority = 100
    type     = "RateLimitRule"
    action   = "Block"
    enabled  = true

    rate_limit_duration_in_minutes = 1
    rate_limit_threshold           = 100

    match_condition {
      match_variable     = "RequestUri"
      operator           = "RegEx"
      match_values       = [".*"]
      negation_condition = false
    }
  }

  # Rate limiting rule - Auth endpoints (stricter)
  custom_rule {
    name     = "RateLimitAuth"
    priority = 90
    type     = "RateLimitRule"
    action   = "Block"
    enabled  = true

    rate_limit_duration_in_minutes = 1
    rate_limit_threshold           = 10

    match_condition {
      match_variable     = "RequestUri"
      operator           = "Contains"
      match_values       = ["/api/auth/", "/auth/"]
      negation_condition = false
    }
  }

  # Rate limiting rule - Chat API (protect OpenAI costs)
  custom_rule {
    name     = "RateLimitChat"
    priority = 80
    type     = "RateLimitRule"
    action   = "Block"
    enabled  = true

    rate_limit_duration_in_minutes = 1
    rate_limit_threshold           = 30

    match_condition {
      match_variable     = "RequestUri"
      operator           = "Contains"
      match_values       = ["/api/chat"]
      negation_condition = false
    }
  }

  # Bot protection
  custom_rule {
    name     = "BlockBadBots"
    priority = 50
    type     = "MatchRule"
    action   = "Block"
    enabled  = true

    match_condition {
      match_variable     = "RequestHeader"
      selector           = "User-Agent"
      operator           = "Contains"
      match_values       = ["curl", "wget", "python-requests", "scrapy", "bot"]
      transforms         = ["Lowercase"]
      negation_condition = false
    }
  }

  # Geo-blocking (optional - uncomment if needed)
  # custom_rule {
  #   name     = "GeoBlock"
  #   priority = 60
  #   type     = "MatchRule"
  #   action   = "Block"
  #   enabled  = true
  #
  #   match_condition {
  #     match_variable     = "RemoteAddr"
  #     operator           = "GeoMatch"
  #     match_values       = ["XX", "YY"]  # Country codes to block
  #     negation_condition = false
  #   }
  # }

  managed_rule {
    type    = "Microsoft_DefaultRuleSet"
    version = "2.1"
    action  = "Block"
  }

  managed_rule {
    type    = "Microsoft_BotManagerRuleSet"
    version = "1.0"
    action  = "Block"
  }
}

# Associate WAF policy with Front Door
resource "azurerm_cdn_frontdoor_security_policy" "pulse_security" {
  name                     = "pulse-security-policy"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.pulse.id

  security_policies {
    firewall {
      cdn_frontdoor_firewall_policy_id = azurerm_cdn_frontdoor_firewall_policy.pulse_waf.id

      association {
        domain {
          cdn_frontdoor_domain_id = azurerm_cdn_frontdoor_custom_domain.pulse.id
        }
        patterns_to_match = ["/*"]
      }
    }
  }
}
```

---

## Function App Rate Limiting

### Python Function Rate Limiter

Create `func/shared/rate_limiter.py`:

```python
"""
PULSE Function App Rate Limiter
Distributed rate limiting using Azure Cache for Redis
"""

import time
import logging
from typing import Optional, Tuple
from dataclasses import dataclass
from functools import wraps
import redis
import azure.functions as func

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Rate limit configuration"""
    max_requests: int
    window_seconds: int
    key_prefix: str = "func_rl"


class RedisRateLimiter:
    """Redis-backed rate limiter for distributed scenarios"""

    def __init__(self, redis_url: str, config: RateLimitConfig):
        self.redis = redis.from_url(redis_url, decode_responses=True)
        self.config = config

    def check(self, identifier: str) -> Tuple[bool, int, int]:
        """
        Check if request is allowed.

        Returns:
            Tuple of (allowed, remaining, retry_after_seconds)
        """
        key = f"{self.config.key_prefix}:{identifier}"
        now = int(time.time())
        window_start = now - self.config.window_seconds

        pipe = self.redis.pipeline()

        # Remove old entries
        pipe.zremrangebyscore(key, 0, window_start)

        # Count current requests
        pipe.zcard(key)

        # Add current request (optimistically)
        pipe.zadd(key, {str(now): now})

        # Set expiry
        pipe.expire(key, self.config.window_seconds)

        results = pipe.execute()
        current_count = results[1]

        if current_count >= self.config.max_requests:
            # Remove the optimistic add
            self.redis.zrem(key, str(now))

            # Calculate retry after
            oldest = self.redis.zrange(key, 0, 0, withscores=True)
            if oldest:
                retry_after = int(oldest[0][1]) + self.config.window_seconds - now
            else:
                retry_after = self.config.window_seconds

            return False, 0, max(1, retry_after)

        remaining = self.config.max_requests - current_count - 1
        return True, remaining, 0


class InMemoryRateLimiter:
    """In-memory rate limiter for single-instance scenarios"""

    def __init__(self, config: RateLimitConfig):
        self.config = config
        self.requests: dict[str, list[float]] = {}

    def check(self, identifier: str) -> Tuple[bool, int, int]:
        """Check if request is allowed."""
        now = time.time()
        window_start = now - self.config.window_seconds

        key = f"{self.config.key_prefix}:{identifier}"

        # Get or create request list
        if key not in self.requests:
            self.requests[key] = []

        # Filter to current window
        self.requests[key] = [
            ts for ts in self.requests[key]
            if ts > window_start
        ]

        if len(self.requests[key]) >= self.config.max_requests:
            # Calculate retry after
            oldest = min(self.requests[key]) if self.requests[key] else now
            retry_after = int(oldest + self.config.window_seconds - now)
            return False, 0, max(1, retry_after)

        # Add current request
        self.requests[key].append(now)
        remaining = self.config.max_requests - len(self.requests[key])

        return True, remaining, 0


# Global rate limiter instance
_rate_limiter: Optional[RedisRateLimiter | InMemoryRateLimiter] = None


def get_rate_limiter(config: RateLimitConfig) -> RedisRateLimiter | InMemoryRateLimiter:
    """Get or create rate limiter instance."""
    global _rate_limiter

    if _rate_limiter is None:
        import os
        redis_url = os.environ.get("REDIS_CONNECTION_STRING")

        if redis_url:
            _rate_limiter = RedisRateLimiter(redis_url, config)
            logger.info("Using Redis-backed rate limiter")
        else:
            _rate_limiter = InMemoryRateLimiter(config)
            logger.warning("Using in-memory rate limiter (not suitable for production)")

    return _rate_limiter


def get_client_ip(req: func.HttpRequest) -> str:
    """Extract client IP from request."""
    # Azure Functions behind Front Door
    forwarded = req.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()

    # Direct connection
    return req.headers.get("X-Real-IP", "unknown")


def rate_limit(
    max_requests: int = 100,
    window_seconds: int = 60,
    key_prefix: str = "func"
):
    """Decorator for rate limiting Azure Functions."""

    def decorator(func_handler):
        config = RateLimitConfig(
            max_requests=max_requests,
            window_seconds=window_seconds,
            key_prefix=key_prefix
        )

        @wraps(func_handler)
        def wrapper(req: func.HttpRequest, *args, **kwargs) -> func.HttpResponse:
            limiter = get_rate_limiter(config)
            client_ip = get_client_ip(req)

            allowed, remaining, retry_after = limiter.check(client_ip)

            if not allowed:
                logger.warning(
                    f"Rate limit exceeded for {client_ip}",
                    extra={"client_ip": client_ip, "retry_after": retry_after}
                )

                return func.HttpResponse(
                    body='{"error": "Rate limit exceeded", "code": "RATE_LIMIT_EXCEEDED"}',
                    status_code=429,
                    headers={
                        "Content-Type": "application/json",
                        "Retry-After": str(retry_after),
                        "X-RateLimit-Remaining": "0",
                    },
                    mimetype="application/json"
                )

            response = func_handler(req, *args, **kwargs)

            # Add rate limit headers to response
            if isinstance(response, func.HttpResponse):
                response.headers["X-RateLimit-Remaining"] = str(remaining)

            return response

        return wrapper
    return decorator


# Pre-configured decorators for common use cases
chat_rate_limit = rate_limit(max_requests=20, window_seconds=60, key_prefix="chat")
api_rate_limit = rate_limit(max_requests=100, window_seconds=60, key_prefix="api")
auth_rate_limit = rate_limit(max_requests=10, window_seconds=60, key_prefix="auth")
```

### Apply to Function

Update `func/chat_function/__init__.py`:

```python
import azure.functions as func
from shared.rate_limiter import chat_rate_limit


@chat_rate_limit
def main(req: func.HttpRequest) -> func.HttpResponse:
    """Chat function with rate limiting."""

    # Your existing function logic here

    return func.HttpResponse(
        body='{"message": "Hello"}',
        status_code=200,
        mimetype="application/json"
    )
```

---

## Redis-Based Distributed Rate Limiting

### Terraform Configuration

Create `infra/modules/redis/main.tf`:

```hcl
# Azure Cache for Redis for distributed rate limiting

resource "azurerm_redis_cache" "pulse" {
  name                = "redis-pulse-${var.environment}"
  location            = var.location
  resource_group_name = var.resource_group_name
  capacity            = var.redis_capacity
  family              = var.redis_family
  sku_name            = var.redis_sku
  enable_non_ssl_port = false
  minimum_tls_version = "1.2"

  redis_configuration {
    maxmemory_policy = "volatile-lru"
  }

  # Private endpoint for security
  public_network_access_enabled = false

  tags = var.tags
}

# Private endpoint for Redis
resource "azurerm_private_endpoint" "redis" {
  name                = "pe-redis-pulse-${var.environment}"
  location            = var.location
  resource_group_name = var.resource_group_name
  subnet_id           = var.private_endpoint_subnet_id

  private_service_connection {
    name                           = "redis-connection"
    private_connection_resource_id = azurerm_redis_cache.pulse.id
    is_manual_connection           = false
    subresource_names              = ["redisCache"]
  }

  private_dns_zone_group {
    name                 = "redis-dns"
    private_dns_zone_ids = [var.redis_private_dns_zone_id]
  }
}

# Output connection string for applications
output "redis_connection_string" {
  value     = "rediss://:${azurerm_redis_cache.pulse.primary_access_key}@${azurerm_redis_cache.pulse.hostname}:${azurerm_redis_cache.pulse.ssl_port}"
  sensitive = true
}
```

### TypeScript Redis Rate Limiter

Create `ui/lib/redis-rate-limiter.ts`:

```typescript
/**
 * PULSE Redis Rate Limiter
 * Distributed rate limiting using Azure Cache for Redis
 */

import { Redis } from 'ioredis';
import { RateLimitStore, RateLimitConfig, RateLimitResult } from './rate-limiter';

export class RedisRateLimitStore implements RateLimitStore {
  private redis: Redis;
  private keyPrefix: string;

  constructor(redisUrl: string, keyPrefix: string = 'rl') {
    this.redis = new Redis(redisUrl, {
      tls: { rejectUnauthorized: false },
      retryDelayOnFailover: 100,
      maxRetriesPerRequest: 3,
    });
    this.keyPrefix = keyPrefix;
  }

  async increment(key: string, windowMs: number): Promise<{ count: number; resetTime: number }> {
    const fullKey = `${this.keyPrefix}:${key}`;
    const now = Date.now();
    const windowStart = now - windowMs;
    const windowEnd = now + windowMs;

    // Use sorted set for sliding window
    const pipeline = this.redis.pipeline();

    // Remove expired entries
    pipeline.zremrangebyscore(fullKey, 0, windowStart);

    // Add current request
    pipeline.zadd(fullKey, now, `${now}:${Math.random()}`);

    // Count requests in window
    pipeline.zcard(fullKey);

    // Set expiry
    pipeline.pexpire(fullKey, windowMs);

    const results = await pipeline.exec();

    if (!results) {
      throw new Error('Redis pipeline failed');
    }

    const count = results[2]?.[1] as number || 0;

    return {
      count,
      resetTime: windowEnd,
    };
  }

  async get(key: string): Promise<{ count: number; resetTime: number } | null> {
    const fullKey = `${this.keyPrefix}:${key}`;
    const count = await this.redis.zcard(fullKey);

    if (count === 0) {
      return null;
    }

    const ttl = await this.redis.pttl(fullKey);

    return {
      count,
      resetTime: Date.now() + ttl,
    };
  }

  async reset(key: string): Promise<void> {
    const fullKey = `${this.keyPrefix}:${key}`;
    await this.redis.del(fullKey);
  }

  async close(): Promise<void> {
    await this.redis.quit();
  }
}

/**
 * Create Redis-backed rate limiter
 */
export function createRedisRateLimiter(config: RateLimitConfig & { redisUrl: string }) {
  const store = new RedisRateLimitStore(config.redisUrl, config.keyPrefix);

  return {
    async check(identifier: string): Promise<RateLimitResult> {
      const { count, resetTime } = await store.increment(identifier, config.windowMs);
      const allowed = count <= config.maxRequests;
      const remaining = Math.max(0, config.maxRequests - count);
      const retryAfter = allowed ? undefined : Math.ceil((resetTime - Date.now()) / 1000);

      return { allowed, remaining, resetTime, retryAfter };
    },
    store,
  };
}
```

---

## AI/LLM Specific Rate Limiting

### Token-Based Rate Limiting

Create `ui/lib/token-rate-limiter.ts`:

```typescript
/**
 * PULSE Token-Based Rate Limiter
 * Rate limiting based on token consumption for AI/LLM APIs
 */

import { RateLimitStore, MemoryRateLimitStore, RateLimitResult } from './rate-limiter';

export interface TokenRateLimitConfig {
  /** Maximum tokens allowed per window */
  maxTokens: number;
  /** Window size in milliseconds */
  windowMs: number;
  /** Key prefix */
  keyPrefix?: string;
}

interface TokenUsage {
  promptTokens: number;
  completionTokens: number;
  totalTokens: number;
}

/**
 * Token-based rate limiter for AI/LLM requests
 */
export class TokenRateLimiter {
  private store: Map<string, { tokens: number; resetTime: number }> = new Map();
  private config: Required<TokenRateLimitConfig>;

  constructor(config: TokenRateLimitConfig) {
    this.config = {
      maxTokens: config.maxTokens,
      windowMs: config.windowMs,
      keyPrefix: config.keyPrefix || 'token_rl',
    };
  }

  /**
   * Check if request is allowed (pre-request check with estimated tokens)
   */
  async checkPreRequest(identifier: string, estimatedTokens: number): Promise<RateLimitResult> {
    const key = `${this.config.keyPrefix}:${identifier}`;
    const now = Date.now();
    const entry = this.store.get(key);

    // Reset if window expired
    if (!entry || now >= entry.resetTime) {
      if (estimatedTokens <= this.config.maxTokens) {
        return {
          allowed: true,
          remaining: this.config.maxTokens - estimatedTokens,
          resetTime: now + this.config.windowMs,
        };
      }
    }

    const currentTokens = entry?.tokens || 0;
    const remaining = this.config.maxTokens - currentTokens;

    if (estimatedTokens <= remaining) {
      return {
        allowed: true,
        remaining: remaining - estimatedTokens,
        resetTime: entry?.resetTime || now + this.config.windowMs,
      };
    }

    const resetTime = entry?.resetTime || now + this.config.windowMs;
    return {
      allowed: false,
      remaining: 0,
      resetTime,
      retryAfter: Math.ceil((resetTime - now) / 1000),
    };
  }

  /**
   * Record actual token usage (post-request)
   */
  async recordUsage(identifier: string, usage: TokenUsage): Promise<void> {
    const key = `${this.config.keyPrefix}:${identifier}`;
    const now = Date.now();
    let entry = this.store.get(key);

    // Reset if window expired
    if (!entry || now >= entry.resetTime) {
      entry = {
        tokens: 0,
        resetTime: now + this.config.windowMs,
      };
    }

    entry.tokens += usage.totalTokens;
    this.store.set(key, entry);
  }

  /**
   * Get current token usage for an identifier
   */
  async getUsage(identifier: string): Promise<{ used: number; remaining: number; resetTime: number }> {
    const key = `${this.config.keyPrefix}:${identifier}`;
    const now = Date.now();
    const entry = this.store.get(key);

    if (!entry || now >= entry.resetTime) {
      return {
        used: 0,
        remaining: this.config.maxTokens,
        resetTime: now + this.config.windowMs,
      };
    }

    return {
      used: entry.tokens,
      remaining: Math.max(0, this.config.maxTokens - entry.tokens),
      resetTime: entry.resetTime,
    };
  }
}

/**
 * Estimate token count for a message
 * Simple approximation: ~4 characters per token
 */
export function estimateTokens(text: string): number {
  return Math.ceil(text.length / 4);
}

/**
 * Estimate tokens for chat messages
 */
export function estimateChatTokens(messages: Array<{ role: string; content: string }>): number {
  let tokens = 0;

  for (const msg of messages) {
    // Add overhead per message (~4 tokens)
    tokens += 4;
    // Add content tokens
    tokens += estimateTokens(msg.content);
    // Add role token
    tokens += 1;
  }

  // Add overhead for response (estimate)
  tokens += 500; // Conservative estimate for response

  return tokens;
}

// Pre-configured token rate limiters
export const tokenLimiters = {
  // 100K tokens per hour
  hourly: new TokenRateLimiter({
    maxTokens: 100000,
    windowMs: 60 * 60 * 1000,
    keyPrefix: 'token_hourly',
  }),
  // 500K tokens per day
  daily: new TokenRateLimiter({
    maxTokens: 500000,
    windowMs: 24 * 60 * 60 * 1000,
    keyPrefix: 'token_daily',
  }),
};
```

---

## Monitoring and Alerting

### Azure Monitor Queries

Create `infra/monitoring/rate-limit-queries.kql`:

```kql
// Rate Limit Monitoring Queries

// 1. Rate limit events over time
customEvents
| where timestamp > ago(24h)
| where name contains "RATE_LIMIT"
| summarize count() by bin(timestamp, 5m), name
| render timechart

// 2. Top rate-limited clients
customEvents
| where timestamp > ago(24h)
| where name == "RATE_LIMIT_EXCEEDED"
| summarize
    violations = count(),
    first_seen = min(timestamp),
    last_seen = max(timestamp)
    by clientId = tostring(customDimensions.clientId)
| order by violations desc
| take 50

// 3. Rate limits by endpoint
customEvents
| where timestamp > ago(24h)
| where name == "RATE_LIMIT_EXCEEDED"
| summarize count() by path = tostring(customDimensions.path)
| order by count_ desc

// 4. Auth rate limits (potential brute force)
customEvents
| where timestamp > ago(1h)
| where name == "AUTH_RATE_LIMIT_EXCEEDED"
| summarize attempts = count() by ip = tostring(customDimensions.ip)
| where attempts > 5
| order by attempts desc

// 5. Token usage trends
customMetrics
| where timestamp > ago(7d)
| where name == "TokensUsed"
| summarize total = sum(value) by bin(timestamp, 1h), userId = tostring(customDimensions.userId)
| render timechart

// 6. Rate limit headroom
customMetrics
| where timestamp > ago(24h)
| where name == "RateLimitRemaining"
| summarize
    avg_remaining = avg(value),
    min_remaining = min(value)
    by bin(timestamp, 1h), endpoint = tostring(customDimensions.endpoint)
| render timechart
```

### Alert Rules

Create `infra/modules/monitoring/rate-limit-alerts.tf`:

```hcl
# Rate Limiting Alert Rules

# High rate of rate limit violations
resource "azurerm_monitor_scheduled_query_rules_alert" "high_rate_limit_violations" {
  name                = "pulse-high-rate-limit-violations"
  location            = var.location
  resource_group_name = var.resource_group_name

  action {
    action_group = [var.alert_action_group_id]
  }

  data_source_id = var.log_analytics_workspace_id
  description    = "High volume of rate limit violations detected"
  enabled        = true

  query = <<-QUERY
    customEvents
    | where timestamp > ago(5m)
    | where name == "RATE_LIMIT_EXCEEDED"
    | summarize count()
  QUERY

  severity    = 2
  frequency   = 5
  time_window = 10

  trigger {
    operator  = "GreaterThan"
    threshold = 50
  }
}

# Potential brute force attack
resource "azurerm_monitor_scheduled_query_rules_alert" "auth_brute_force" {
  name                = "pulse-auth-brute-force"
  location            = var.location
  resource_group_name = var.resource_group_name

  action {
    action_group = [var.alert_action_group_id]
  }

  data_source_id = var.log_analytics_workspace_id
  description    = "Potential brute force attack on auth endpoints"
  enabled        = true

  query = <<-QUERY
    customEvents
    | where timestamp > ago(5m)
    | where name == "AUTH_RATE_LIMIT_EXCEEDED"
    | summarize attempts = count() by ip = tostring(customDimensions.ip)
    | where attempts > 10
  QUERY

  severity    = 1
  frequency   = 5
  time_window = 10

  trigger {
    operator  = "GreaterThan"
    threshold = 0
  }
}

# Token usage spike
resource "azurerm_monitor_metric_alert" "token_usage_spike" {
  name                = "pulse-token-usage-spike"
  resource_group_name = var.resource_group_name
  scopes              = [var.log_analytics_workspace_id]
  description         = "Unusual spike in token consumption"

  criteria {
    metric_namespace = "Azure.ApplicationInsights"
    metric_name      = "TokensUsed"
    aggregation      = "Total"
    operator         = "GreaterThan"
    threshold        = 100000 # 100K tokens in evaluation period
  }

  window_size        = "PT15M"
  frequency          = "PT5M"
  severity           = 2

  action {
    action_group_id = var.alert_action_group_id
  }
}
```

---

## Testing and Validation

### Rate Limit Test Suite

Create `ui/__tests__/rate-limiter.test.ts`:

```typescript
import {
  FixedWindowRateLimiter,
  SlidingWindowRateLimiter,
  TokenBucketRateLimiter,
  CompositeRateLimiter,
  MemoryRateLimitStore,
} from '../lib/rate-limiter';

describe('Rate Limiters', () => {
  describe('FixedWindowRateLimiter', () => {
    it('should allow requests under limit', async () => {
      const limiter = new FixedWindowRateLimiter({
        maxRequests: 10,
        windowMs: 60000,
      });

      for (let i = 0; i < 10; i++) {
        const result = await limiter.check('user1');
        expect(result.allowed).toBe(true);
        expect(result.remaining).toBe(9 - i);
      }
    });

    it('should block requests over limit', async () => {
      const limiter = new FixedWindowRateLimiter({
        maxRequests: 5,
        windowMs: 60000,
      });

      // Use up the limit
      for (let i = 0; i < 5; i++) {
        await limiter.check('user1');
      }

      // Next request should be blocked
      const result = await limiter.check('user1');
      expect(result.allowed).toBe(false);
      expect(result.remaining).toBe(0);
      expect(result.retryAfter).toBeDefined();
    });

    it('should track different users separately', async () => {
      const limiter = new FixedWindowRateLimiter({
        maxRequests: 2,
        windowMs: 60000,
      });

      await limiter.check('user1');
      await limiter.check('user1');

      const user1Result = await limiter.check('user1');
      expect(user1Result.allowed).toBe(false);

      const user2Result = await limiter.check('user2');
      expect(user2Result.allowed).toBe(true);
    });
  });

  describe('SlidingWindowRateLimiter', () => {
    it('should use sliding window correctly', async () => {
      const limiter = new SlidingWindowRateLimiter({
        maxRequests: 3,
        windowMs: 1000, // 1 second
      });

      // Make 3 requests
      await limiter.check('user1');
      await limiter.check('user1');
      await limiter.check('user1');

      // 4th should be blocked
      let result = await limiter.check('user1');
      expect(result.allowed).toBe(false);

      // Wait for window to slide
      await new Promise(resolve => setTimeout(resolve, 1100));

      // Should be allowed again
      result = await limiter.check('user1');
      expect(result.allowed).toBe(true);
    });
  });

  describe('TokenBucketRateLimiter', () => {
    it('should allow burst up to max tokens', async () => {
      const limiter = new TokenBucketRateLimiter({
        maxTokens: 10,
        refillRatePerSecond: 1,
      });

      // Burst 10 requests
      for (let i = 0; i < 10; i++) {
        const result = await limiter.check('user1');
        expect(result.allowed).toBe(true);
      }

      // 11th should be blocked
      const result = await limiter.check('user1');
      expect(result.allowed).toBe(false);
    });

    it('should refill tokens over time', async () => {
      const limiter = new TokenBucketRateLimiter({
        maxTokens: 5,
        refillRatePerSecond: 5, // 1 token per 200ms
      });

      // Use all tokens
      for (let i = 0; i < 5; i++) {
        await limiter.check('user1');
      }

      // Wait for 1 token to refill
      await new Promise(resolve => setTimeout(resolve, 250));

      const result = await limiter.check('user1');
      expect(result.allowed).toBe(true);
    });
  });

  describe('CompositeRateLimiter', () => {
    it('should enforce all limits', async () => {
      const composite = new CompositeRateLimiter([
        {
          name: 'per-minute',
          limiter: new FixedWindowRateLimiter({
            maxRequests: 5,
            windowMs: 60000,
          }),
        },
        {
          name: 'per-hour',
          limiter: new FixedWindowRateLimiter({
            maxRequests: 10,
            windowMs: 3600000,
          }),
        },
      ]);

      // Make 5 requests (hits per-minute limit)
      for (let i = 0; i < 5; i++) {
        await composite.check('user1');
      }

      const result = await composite.check('user1');
      expect(result.allowed).toBe(false);
      expect((result as any).failedLimiter).toBe('per-minute');
    });
  });
});
```

### Integration Test Script

Create `scripts/test-rate-limits.sh`:

```bash
#!/bin/bash
# PULSE Rate Limit Integration Tests

set -e

API_URL="${1:-http://localhost:3000}"
ENDPOINT="${2:-/api/chat}"
REQUESTS="${3:-50}"
CONCURRENT="${4:-10}"

echo "Testing rate limits on: $API_URL$ENDPOINT"
echo "Requests: $REQUESTS, Concurrent: $CONCURRENT"
echo ""

# Function to make request and report
make_request() {
    local id=$1
    local response=$(curl -s -w "\n%{http_code}" -X POST "$API_URL$ENDPOINT" \
        -H "Content-Type: application/json" \
        -d '{"message": "test"}')

    local status=$(echo "$response" | tail -n1)
    local body=$(echo "$response" | sed '$d')

    if [ "$status" == "429" ]; then
        echo "Request $id: RATE LIMITED (429)"
        local retry_after=$(echo "$body" | jq -r '.retryAfter // "unknown"')
        echo "  Retry-After: $retry_after seconds"
    elif [ "$status" == "200" ]; then
        echo "Request $id: OK (200)"
    else
        echo "Request $id: ERROR ($status)"
    fi
}

# Sequential test
echo "=== Sequential Test ==="
rate_limited=0
for i in $(seq 1 $REQUESTS); do
    result=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$API_URL$ENDPOINT" \
        -H "Content-Type: application/json" \
        -d '{"message": "test"}')

    if [ "$result" == "429" ]; then
        ((rate_limited++))
    fi

    echo -n "."
done
echo ""
echo "Rate limited: $rate_limited out of $REQUESTS requests"
echo ""

# Burst test
echo "=== Burst Test (Concurrent: $CONCURRENT) ==="
for i in $(seq 1 $CONCURRENT); do
    make_request $i &
done
wait

echo ""
echo "=== Test Complete ==="
```

---

## Migration Checklist

### Phase 1: Application Layer

- [ ] Create `ui/lib/rate-limiter.ts` with rate limiting classes
- [ ] Create `ui/lib/rate-limit-middleware.ts` for API routes
- [ ] Create `ui/lib/token-rate-limiter.ts` for AI token limits
- [ ] Update API routes to use rate limiting middleware
- [ ] Add rate limit headers to responses

### Phase 2: Infrastructure Layer

- [ ] Deploy Azure Cache for Redis for distributed limiting
- [ ] Configure Azure Front Door WAF rate limiting rules
- [ ] Set up Azure API Management rate limiting policies
- [ ] Update Terraform with rate limiting resources

### Phase 3: Function App

- [ ] Create `func/shared/rate_limiter.py`
- [ ] Apply rate limiting decorators to functions
- [ ] Configure Redis connection for functions

### Phase 4: Monitoring

- [ ] Deploy Log Analytics queries
- [ ] Create Azure Monitor alert rules
- [ ] Set up dashboards for rate limit metrics
- [ ] Configure notification channels

### Phase 5: Testing

- [ ] Run unit tests for rate limiters
- [ ] Execute integration tests
- [ ] Perform load testing to validate limits
- [ ] Test failover scenarios

---

## Best Practices Summary

1. **Defense in Depth**: Apply rate limiting at multiple layers
2. **User-Based Limits**: Prefer user ID over IP when authenticated
3. **Graceful Degradation**: Return helpful error messages with retry-after
4. **Token Counting**: For AI/LLM, limit by tokens not just requests
5. **Monitoring**: Track rate limit events for security analysis
6. **Tuning**: Start conservative, adjust based on usage patterns
7. **Documentation**: Publish rate limits in API documentation

---

## Related Documents

- [securedbydesign.md](securedbydesign.md) - Overall security assessment
- [promptsecurity.md](promptsecurity.md) - Prompt injection protection
- [wafconfig.md](wafconfig.md) - Web Application Firewall configuration
- [corsconfig.md](corsconfig.md) - CORS security configuration
