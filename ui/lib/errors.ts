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
    if (msg.includes('not found')) return 'The requested resource was not found.';
    if (msg.includes('rate limit')) return 'Too many requests. Please slow down.';
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

/**
 * Create an error response with specific status code
 */
export function errorResponse(message: string, status: number = 500): Response {
  return new Response(
    JSON.stringify({ error: message }),
    { status, headers: { 'Content-Type': 'application/json' } }
  );
}
