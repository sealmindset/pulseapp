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
 * Rate limit exceeded response
 */
export function rateLimitResponse(): Response {
  return new Response(
    JSON.stringify({
      error: 'Too many requests',
      message: 'Please slow down and try again in a moment',
    }),
    {
      status: 429,
      headers: {
        'Content-Type': 'application/json',
        'Retry-After': '60',
      },
    }
  );
}

// Cleanup old entries periodically (every 5 minutes)
if (typeof setInterval !== 'undefined') {
  setInterval(() => {
    const now = Date.now();
    for (const [key, entry] of store.entries()) {
      if (now - entry.windowStart > 300000) {
        store.delete(key);
      }
    }
  }, 300000);
}
