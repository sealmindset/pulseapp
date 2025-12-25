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
  | 'RATE_LIMITED'
  | 'ERROR';

interface AuditEvent {
  timestamp: string;
  action: AuditAction;
  userId?: string;
  email?: string;
  ip?: string;
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
    ip?: string;
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

/**
 * Extract IP from request for audit logging
 */
export function getAuditIp(req: Request): string {
  const forwarded = req.headers.get('x-forwarded-for');
  return forwarded ? forwarded.split(',')[0].trim() : 'unknown';
}

// Convenience functions
export const auditLog = {
  login: (email: string, userId?: string, ip?: string) =>
    audit('LOGIN', { email, userId, ip }),

  loginFailed: (email: string, reason?: string, ip?: string) =>
    audit('LOGIN_FAILED', { email, ip, details: { reason } }),

  logout: (email: string, ip?: string) =>
    audit('LOGOUT', { email, ip }),

  sessionStart: (userId: string, sessionId: string, ip?: string) =>
    audit('SESSION_START', { userId, ip, details: { sessionId } }),

  sessionEnd: (sessionId: string, ip?: string) =>
    audit('SESSION_END', { ip, details: { sessionId } }),

  adminAction: (
    userId: string,
    action: string,
    ip?: string
  ) => audit('ADMIN_USER_UPDATE', { userId, ip, details: { action } }),

  rateLimited: (identifier: string, endpoint: string, ip?: string) =>
    audit('RATE_LIMITED', { ip, details: { identifier, endpoint } }),

  error: (context: string, error: unknown, ip?: string) =>
    audit('ERROR', { ip, details: { context, error: String(error) } }),
};
