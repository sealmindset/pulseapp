/**
 * PULSE Training Platform Logger
 *
 * A centralized logging utility that:
 * 1. Logs to console (always)
 * 2. Forwards logs to Cribl Stream (when configured)
 *
 * Usage:
 *   import { logger } from '@/lib/logger';
 *
 *   logger.info('User logged in', { userId: '123', source: 'auth' });
 *   logger.error('Failed to load avatars', { error: err.message, source: 'avatar-service' });
 *   logger.behavioral('Training session completed', { userId: '123', sessionId: 'abc', score: 85 });
 */

type LogLevel = "DEBUG" | "INFO" | "WARN" | "ERROR" | "FATAL";
type LogType = "system" | "application" | "behavioral";

interface LogOptions {
  source?: string;
  userId?: string;
  sessionId?: string;
  traceId?: string;
  metadata?: Record<string, unknown>;
}

interface LogEntry {
  timestamp: string;
  level: LogLevel;
  type: LogType;
  source: string;
  message: string;
  metadata?: Record<string, unknown>;
  userId?: string;
  sessionId?: string;
  traceId?: string;
}

class Logger {
  private static instance: Logger;
  private forwardingEnabled: boolean = true;

  private constructor() {}

  static getInstance(): Logger {
    if (!Logger.instance) {
      Logger.instance = new Logger();
    }
    return Logger.instance;
  }

  /**
   * Enable or disable log forwarding to Cribl
   */
  setForwardingEnabled(enabled: boolean) {
    this.forwardingEnabled = enabled;
  }

  /**
   * Log a message with the specified level and type
   */
  private async log(
    level: LogLevel,
    type: LogType,
    message: string,
    options: LogOptions = {}
  ) {
    const entry: LogEntry = {
      timestamp: new Date().toISOString(),
      level,
      type,
      source: options.source || "PULSE-Training-App",
      message,
      metadata: options.metadata,
      userId: options.userId,
      sessionId: options.sessionId,
      traceId: options.traceId,
    };

    // Always log to console
    this.logToConsole(entry);

    // Forward to Cribl if enabled (client-side only)
    if (this.forwardingEnabled && typeof window !== "undefined") {
      this.forwardToCribl(entry).catch((err) => {
        console.warn("Failed to forward log to Cribl:", err);
      });
    }
  }

  /**
   * Log to console with appropriate styling
   */
  private logToConsole(entry: LogEntry) {
    const prefix = `[${entry.timestamp}] [${entry.level}] [${entry.type}]`;
    const source = entry.source ? `[${entry.source}]` : "";
    const fullMessage = `${prefix} ${source} ${entry.message}`;

    const metadata = {
      ...(entry.metadata || {}),
      ...(entry.userId && { userId: entry.userId }),
      ...(entry.sessionId && { sessionId: entry.sessionId }),
      ...(entry.traceId && { traceId: entry.traceId }),
    };

    const hasMetadata = Object.keys(metadata).length > 0;

    switch (entry.level) {
      case "DEBUG":
        hasMetadata ? console.debug(fullMessage, metadata) : console.debug(fullMessage);
        break;
      case "INFO":
        hasMetadata ? console.info(fullMessage, metadata) : console.info(fullMessage);
        break;
      case "WARN":
        hasMetadata ? console.warn(fullMessage, metadata) : console.warn(fullMessage);
        break;
      case "ERROR":
      case "FATAL":
        hasMetadata ? console.error(fullMessage, metadata) : console.error(fullMessage);
        break;
    }
  }

  /**
   * Forward log to Cribl via the internal API
   */
  private async forwardToCribl(entry: LogEntry) {
    try {
      await fetch("/api/admin/logs/forward", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(entry),
      });
    } catch {
      // Silently fail - we don't want logging failures to break the app
    }
  }

  // ============= System Logs =============

  /**
   * Log system-level debug information
   */
  debugSystem(message: string, options?: LogOptions) {
    return this.log("DEBUG", "system", message, options);
  }

  /**
   * Log system-level info
   */
  infoSystem(message: string, options?: LogOptions) {
    return this.log("INFO", "system", message, options);
  }

  /**
   * Log system-level warning
   */
  warnSystem(message: string, options?: LogOptions) {
    return this.log("WARN", "system", message, options);
  }

  /**
   * Log system-level error
   */
  errorSystem(message: string, options?: LogOptions) {
    return this.log("ERROR", "system", message, options);
  }

  // ============= Application Logs =============

  /**
   * Log application debug information
   */
  debug(message: string, options?: LogOptions) {
    return this.log("DEBUG", "application", message, options);
  }

  /**
   * Log application info
   */
  info(message: string, options?: LogOptions) {
    return this.log("INFO", "application", message, options);
  }

  /**
   * Log application warning
   */
  warn(message: string, options?: LogOptions) {
    return this.log("WARN", "application", message, options);
  }

  /**
   * Log application error
   */
  error(message: string, options?: LogOptions) {
    return this.log("ERROR", "application", message, options);
  }

  /**
   * Log fatal application error
   */
  fatal(message: string, options?: LogOptions) {
    return this.log("FATAL", "application", message, options);
  }

  // ============= Behavioral Logs =============

  /**
   * Log behavioral/training event (user progress, scores, etc.)
   */
  behavioral(message: string, options?: LogOptions) {
    return this.log("INFO", "behavioral", message, options);
  }

  /**
   * Log behavioral warning (unusual patterns, edge cases)
   */
  behavioralWarn(message: string, options?: LogOptions) {
    return this.log("WARN", "behavioral", message, options);
  }

  /**
   * Log behavioral error (training failures, scoring errors)
   */
  behavioralError(message: string, options?: LogOptions) {
    return this.log("ERROR", "behavioral", message, options);
  }
}

// Export singleton instance
export const logger = Logger.getInstance();

// Export types for consumers
export type { LogLevel, LogType, LogOptions, LogEntry };
