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
    'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-Function-Key',
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

/**
 * Add CORS headers to a response
 */
export function withCors(response: Response, requestOrigin: string | null): Response {
  const corsHeaders = getCorsHeaders(requestOrigin);
  const newHeaders = new Headers(response.headers);

  Object.entries(corsHeaders).forEach(([key, value]) => {
    newHeaders.set(key, value);
  });

  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: newHeaders,
  });
}
