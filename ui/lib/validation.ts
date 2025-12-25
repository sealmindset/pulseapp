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
export function validateChatRequest(body: unknown): { valid: boolean; error?: string; data?: { sessionId: string; message: string; persona: string } } {
  if (!body || typeof body !== 'object') {
    return { valid: false, error: 'Invalid request body' };
  }

  const { sessionId, message, persona } = body as {
    sessionId?: string;
    message?: string;
    persona?: string;
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

  return {
    valid: true,
    data: {
      sessionId,
      message: message!,
      persona: persona || 'Relater',
    },
  };
}

/**
 * Validate session complete request
 */
export function validateSessionComplete(body: unknown): { valid: boolean; error?: string } {
  if (!body || typeof body !== 'object') {
    return { valid: false, error: 'Invalid request body' };
  }

  const { sessionId } = body as { sessionId?: string };

  if (!sessionId || !isValidUUID(sessionId)) {
    return { valid: false, error: 'Invalid session ID' };
  }

  return { valid: true };
}

/**
 * Simple validation error response
 */
export function validationError(error: string): Response {
  return new Response(
    JSON.stringify({ error }),
    {
      status: 400,
      headers: { 'Content-Type': 'application/json' },
    }
  );
}
