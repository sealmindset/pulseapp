# PULSE Session Revocation Implementation Guide

**Version:** 1.0
**Last Updated:** 2025-12-25
**Priority:** MEDIUM
**Related Documents:** [securedbydesign.md](securedbydesign.md), [secretsmanage.md](secretsmanage.md)

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Session Management Architecture](#session-management-architecture)
3. [Token Revocation Strategies](#token-revocation-strategies)
4. [Redis-Based Token Blacklist](#redis-based-token-blacklist)
5. [Database-Based Session Store](#database-based-session-store)
6. [NextAuth.js Session Revocation](#nextauthjs-session-revocation)
7. [Forced Logout Implementation](#forced-logout-implementation)
8. [Multi-Device Session Management](#multi-device-session-management)
9. [Admin Controls](#admin-controls)
10. [Monitoring and Auditing](#monitoring-and-auditing)
11. [Testing and Validation](#testing-and-validation)
12. [Migration Checklist](#migration-checklist)

---

## Executive Summary

Session revocation is essential for security scenarios including:

- **Account compromise** - Force logout of stolen sessions
- **Password changes** - Invalidate all existing sessions
- **User deprovisioning** - Remove access when user leaves
- **Privilege changes** - Revoke access after role changes
- **Security incidents** - Emergency session termination

This guide implements comprehensive session revocation for the PULSE application using NextAuth.js with Redis-backed session storage.

---

## Session Management Architecture

### Current State vs Target State

| Aspect | Current State | Target State |
|--------|---------------|--------------|
| Session Storage | JWT only (stateless) | JWT + Redis/DB session store |
| Revocation | Not possible | Immediate revocation |
| Multi-device | No visibility | Full visibility and control |
| Forced logout | Not available | Admin and user controls |
| Audit trail | None | Complete session history |

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Client Browser                               │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    Session Cookie (JWT)                      │    │
│  │    Contains: userId, email, sessionId, exp                   │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         Next.js Application                          │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    NextAuth.js Middleware                    │    │
│  │    1. Extract JWT from cookie                                │    │
│  │    2. Verify signature                                       │    │
│  │    3. Check session validity against store                   │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
┌───────────────────────────────┐   ┌───────────────────────────────┐
│         Redis Cache           │   │      PostgreSQL Database       │
│  ┌─────────────────────────┐  │   │  ┌─────────────────────────┐  │
│  │   Session Blacklist     │  │   │  │     Sessions Table       │  │
│  │   (fast lookup)         │  │   │  │   (persistent store)     │  │
│  │                         │  │   │  │                          │  │
│  │   revoked:sessionId     │  │   │  │   id, userId, token,     │  │
│  │   user_sessions:userId  │  │   │  │   device, ip, created,   │  │
│  │                         │  │   │  │   lastActive, revoked    │  │
│  └─────────────────────────┘  │   │  └─────────────────────────┘  │
└───────────────────────────────┘   └───────────────────────────────┘
```

---

## Token Revocation Strategies

### Strategy Comparison

| Strategy | Pros | Cons | Use Case |
|----------|------|------|----------|
| Short-lived tokens | Simple, no storage | Frequent refresh needed | Low-risk apps |
| Blacklist (Redis) | Fast lookup, scalable | Storage grows | High-traffic apps |
| Whitelist (DB) | Positive validation | Every request hits DB | High-security apps |
| Hybrid | Best of both | More complex | Enterprise apps |

### Recommended: Hybrid Approach

1. **Short-lived JWTs** (15 minutes) for access
2. **Long-lived refresh tokens** stored in database
3. **Redis blacklist** for immediate revocation
4. **Database session table** for audit trail

---

## Redis-Based Token Blacklist

### Create Session Store Module

Create `ui/lib/session-store.ts`:

```typescript
/**
 * PULSE Session Store
 * Redis-backed session management with revocation support
 */

import { Redis } from 'ioredis';
import { v4 as uuidv4 } from 'uuid';

export interface Session {
  id: string;
  userId: string;
  email: string;
  deviceInfo: string;
  ipAddress: string;
  userAgent: string;
  createdAt: Date;
  lastActiveAt: Date;
  expiresAt: Date;
  revoked: boolean;
  revokedAt?: Date;
  revokedReason?: string;
}

export interface SessionCreateInput {
  userId: string;
  email: string;
  deviceInfo?: string;
  ipAddress: string;
  userAgent: string;
  expiresInSeconds?: number;
}

const SESSION_PREFIX = 'session:';
const USER_SESSIONS_PREFIX = 'user_sessions:';
const BLACKLIST_PREFIX = 'revoked:';
const DEFAULT_EXPIRY = 7 * 24 * 60 * 60; // 7 days

export class SessionStore {
  private redis: Redis;

  constructor(redisUrl: string) {
    this.redis = new Redis(redisUrl, {
      tls: redisUrl.startsWith('rediss://') ? { rejectUnauthorized: false } : undefined,
      retryDelayOnFailover: 100,
      maxRetriesPerRequest: 3,
    });
  }

  /**
   * Create a new session
   */
  async createSession(input: SessionCreateInput): Promise<Session> {
    const sessionId = uuidv4();
    const now = new Date();
    const expiresInSeconds = input.expiresInSeconds || DEFAULT_EXPIRY;
    const expiresAt = new Date(now.getTime() + expiresInSeconds * 1000);

    const session: Session = {
      id: sessionId,
      userId: input.userId,
      email: input.email,
      deviceInfo: input.deviceInfo || this.parseDeviceInfo(input.userAgent),
      ipAddress: input.ipAddress,
      userAgent: input.userAgent,
      createdAt: now,
      lastActiveAt: now,
      expiresAt,
      revoked: false,
    };

    const pipeline = this.redis.pipeline();

    // Store session data
    pipeline.set(
      `${SESSION_PREFIX}${sessionId}`,
      JSON.stringify(session),
      'EX',
      expiresInSeconds
    );

    // Add to user's session set
    pipeline.sadd(`${USER_SESSIONS_PREFIX}${input.userId}`, sessionId);
    pipeline.expire(`${USER_SESSIONS_PREFIX}${input.userId}`, expiresInSeconds);

    await pipeline.exec();

    return session;
  }

  /**
   * Get session by ID
   */
  async getSession(sessionId: string): Promise<Session | null> {
    // Check blacklist first (fast path for revoked sessions)
    const isRevoked = await this.redis.exists(`${BLACKLIST_PREFIX}${sessionId}`);
    if (isRevoked) {
      return null;
    }

    const data = await this.redis.get(`${SESSION_PREFIX}${sessionId}`);
    if (!data) {
      return null;
    }

    const session = JSON.parse(data) as Session;

    // Check if session is expired or revoked
    if (session.revoked || new Date(session.expiresAt) < new Date()) {
      return null;
    }

    return session;
  }

  /**
   * Validate session and update last active time
   */
  async validateSession(sessionId: string): Promise<Session | null> {
    const session = await this.getSession(sessionId);
    if (!session) {
      return null;
    }

    // Update last active time
    session.lastActiveAt = new Date();
    await this.redis.set(
      `${SESSION_PREFIX}${sessionId}`,
      JSON.stringify(session),
      'KEEPTTL'
    );

    return session;
  }

  /**
   * Revoke a specific session
   */
  async revokeSession(
    sessionId: string,
    reason: string = 'User logout'
  ): Promise<boolean> {
    const session = await this.getSession(sessionId);
    if (!session) {
      return false;
    }

    const pipeline = this.redis.pipeline();

    // Add to blacklist (faster lookup)
    const remainingTtl = Math.max(
      Math.ceil((new Date(session.expiresAt).getTime() - Date.now()) / 1000),
      3600 // Keep at least 1 hour
    );
    pipeline.set(`${BLACKLIST_PREFIX}${sessionId}`, reason, 'EX', remainingTtl);

    // Update session record
    session.revoked = true;
    session.revokedAt = new Date();
    session.revokedReason = reason;
    pipeline.set(`${SESSION_PREFIX}${sessionId}`, JSON.stringify(session), 'EX', remainingTtl);

    // Remove from user's active sessions
    pipeline.srem(`${USER_SESSIONS_PREFIX}${session.userId}`, sessionId);

    await pipeline.exec();

    return true;
  }

  /**
   * Revoke all sessions for a user
   */
  async revokeAllUserSessions(
    userId: string,
    reason: string = 'User requested logout from all devices',
    excludeSessionId?: string
  ): Promise<number> {
    const sessionIds = await this.redis.smembers(`${USER_SESSIONS_PREFIX}${userId}`);
    let revokedCount = 0;

    for (const sessionId of sessionIds) {
      if (excludeSessionId && sessionId === excludeSessionId) {
        continue;
      }
      const revoked = await this.revokeSession(sessionId, reason);
      if (revoked) {
        revokedCount++;
      }
    }

    return revokedCount;
  }

  /**
   * Get all active sessions for a user
   */
  async getUserSessions(userId: string): Promise<Session[]> {
    const sessionIds = await this.redis.smembers(`${USER_SESSIONS_PREFIX}${userId}`);
    const sessions: Session[] = [];

    for (const sessionId of sessionIds) {
      const session = await this.getSession(sessionId);
      if (session && !session.revoked) {
        sessions.push(session);
      }
    }

    // Sort by last active time (most recent first)
    return sessions.sort(
      (a, b) => new Date(b.lastActiveAt).getTime() - new Date(a.lastActiveAt).getTime()
    );
  }

  /**
   * Check if a session is revoked
   */
  async isSessionRevoked(sessionId: string): Promise<boolean> {
    return (await this.redis.exists(`${BLACKLIST_PREFIX}${sessionId}`)) === 1;
  }

  /**
   * Extend session expiry
   */
  async extendSession(sessionId: string, additionalSeconds: number): Promise<boolean> {
    const session = await this.getSession(sessionId);
    if (!session) {
      return false;
    }

    session.expiresAt = new Date(
      new Date(session.expiresAt).getTime() + additionalSeconds * 1000
    );

    await this.redis.set(
      `${SESSION_PREFIX}${sessionId}`,
      JSON.stringify(session),
      'EX',
      Math.ceil((session.expiresAt.getTime() - Date.now()) / 1000)
    );

    return true;
  }

  /**
   * Parse device info from User-Agent
   */
  private parseDeviceInfo(userAgent: string): string {
    // Simple device detection
    if (/iPhone|iPad|iPod/.test(userAgent)) {
      return 'iOS Device';
    }
    if (/Android/.test(userAgent)) {
      return 'Android Device';
    }
    if (/Windows/.test(userAgent)) {
      return 'Windows PC';
    }
    if (/Macintosh/.test(userAgent)) {
      return 'Mac';
    }
    if (/Linux/.test(userAgent)) {
      return 'Linux PC';
    }
    return 'Unknown Device';
  }

  /**
   * Clean up expired sessions (maintenance task)
   */
  async cleanup(): Promise<number> {
    // Redis handles expiry automatically
    // This method is for additional cleanup if needed
    return 0;
  }

  /**
   * Close connection
   */
  async close(): Promise<void> {
    await this.redis.quit();
  }
}

// Singleton instance
let sessionStore: SessionStore | null = null;

export function getSessionStore(): SessionStore {
  if (!sessionStore) {
    const redisUrl = process.env.REDIS_URL || process.env.REDIS_CONNECTION_STRING;
    if (!redisUrl) {
      throw new Error('Redis connection string not configured');
    }
    sessionStore = new SessionStore(redisUrl);
  }
  return sessionStore;
}
```

---

## Database-Based Session Store

### Session Table Schema

Create `infra/migrations/003_sessions.sql`:

```sql
-- Session management tables for PULSE

-- Sessions table
CREATE TABLE IF NOT EXISTS sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(64) NOT NULL,
    device_info VARCHAR(255),
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_active_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    revoked BOOLEAN NOT NULL DEFAULT FALSE,
    revoked_at TIMESTAMPTZ,
    revoked_reason VARCHAR(255),
    revoked_by UUID REFERENCES users(id),

    CONSTRAINT sessions_token_hash_unique UNIQUE (token_hash)
);

-- Indexes
CREATE INDEX idx_sessions_user_id ON sessions(user_id);
CREATE INDEX idx_sessions_token_hash ON sessions(token_hash);
CREATE INDEX idx_sessions_expires_at ON sessions(expires_at);
CREATE INDEX idx_sessions_user_active ON sessions(user_id, revoked, expires_at)
    WHERE revoked = FALSE AND expires_at > NOW();

-- Session audit log
CREATE TABLE IF NOT EXISTS session_audit_log (
    id BIGSERIAL PRIMARY KEY,
    session_id UUID REFERENCES sessions(id),
    user_id UUID NOT NULL REFERENCES users(id),
    action VARCHAR(50) NOT NULL,
    ip_address INET,
    user_agent TEXT,
    details JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_session_audit_user_id ON session_audit_log(user_id);
CREATE INDEX idx_session_audit_created_at ON session_audit_log(created_at);

-- Function to clean up expired sessions
CREATE OR REPLACE FUNCTION cleanup_expired_sessions()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    WITH deleted AS (
        DELETE FROM sessions
        WHERE expires_at < NOW() - INTERVAL '7 days'
        OR (revoked = TRUE AND revoked_at < NOW() - INTERVAL '30 days')
        RETURNING id
    )
    SELECT COUNT(*) INTO deleted_count FROM deleted;

    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Create a function to revoke all sessions for a user
CREATE OR REPLACE FUNCTION revoke_user_sessions(
    p_user_id UUID,
    p_reason VARCHAR(255) DEFAULT 'Admin action',
    p_revoked_by UUID DEFAULT NULL,
    p_exclude_session_id UUID DEFAULT NULL
)
RETURNS INTEGER AS $$
DECLARE
    revoked_count INTEGER;
BEGIN
    UPDATE sessions
    SET
        revoked = TRUE,
        revoked_at = NOW(),
        revoked_reason = p_reason,
        revoked_by = p_revoked_by
    WHERE user_id = p_user_id
    AND revoked = FALSE
    AND (p_exclude_session_id IS NULL OR id != p_exclude_session_id);

    GET DIAGNOSTICS revoked_count = ROW_COUNT;

    -- Log the action
    INSERT INTO session_audit_log (user_id, action, details)
    VALUES (
        p_user_id,
        'REVOKE_ALL',
        jsonb_build_object(
            'reason', p_reason,
            'revoked_by', p_revoked_by,
            'count', revoked_count
        )
    );

    RETURN revoked_count;
END;
$$ LANGUAGE plpgsql;
```

### Database Session Repository

Create `ui/lib/session-repository.ts`:

```typescript
/**
 * PULSE Session Repository
 * PostgreSQL-backed session persistence
 */

import { Pool } from 'pg';
import crypto from 'crypto';

export interface DbSession {
  id: string;
  userId: string;
  tokenHash: string;
  deviceInfo: string | null;
  ipAddress: string | null;
  userAgent: string | null;
  createdAt: Date;
  lastActiveAt: Date;
  expiresAt: Date;
  revoked: boolean;
  revokedAt: Date | null;
  revokedReason: string | null;
  revokedBy: string | null;
}

export class SessionRepository {
  private pool: Pool;

  constructor(connectionString: string) {
    this.pool = new Pool({
      connectionString,
      ssl: process.env.NODE_ENV === 'production' ? { rejectUnauthorized: false } : false,
    });
  }

  /**
   * Hash token for storage
   */
  private hashToken(token: string): string {
    return crypto.createHash('sha256').update(token).digest('hex');
  }

  /**
   * Create a new session
   */
  async create(params: {
    userId: string;
    token: string;
    deviceInfo?: string;
    ipAddress?: string;
    userAgent?: string;
    expiresAt: Date;
  }): Promise<DbSession> {
    const result = await this.pool.query(
      `INSERT INTO sessions (user_id, token_hash, device_info, ip_address, user_agent, expires_at)
       VALUES ($1, $2, $3, $4::inet, $5, $6)
       RETURNING *`,
      [
        params.userId,
        this.hashToken(params.token),
        params.deviceInfo || null,
        params.ipAddress || null,
        params.userAgent || null,
        params.expiresAt,
      ]
    );

    await this.logAudit(params.userId, 'SESSION_CREATED', params.ipAddress, params.userAgent, {
      sessionId: result.rows[0].id,
    });

    return this.mapRow(result.rows[0]);
  }

  /**
   * Get session by token
   */
  async getByToken(token: string): Promise<DbSession | null> {
    const result = await this.pool.query(
      `SELECT * FROM sessions
       WHERE token_hash = $1
       AND revoked = FALSE
       AND expires_at > NOW()`,
      [this.hashToken(token)]
    );

    return result.rows[0] ? this.mapRow(result.rows[0]) : null;
  }

  /**
   * Get session by ID
   */
  async getById(id: string): Promise<DbSession | null> {
    const result = await this.pool.query(
      `SELECT * FROM sessions WHERE id = $1`,
      [id]
    );

    return result.rows[0] ? this.mapRow(result.rows[0]) : null;
  }

  /**
   * Get all active sessions for a user
   */
  async getByUserId(userId: string): Promise<DbSession[]> {
    const result = await this.pool.query(
      `SELECT * FROM sessions
       WHERE user_id = $1
       AND revoked = FALSE
       AND expires_at > NOW()
       ORDER BY last_active_at DESC`,
      [userId]
    );

    return result.rows.map(this.mapRow);
  }

  /**
   * Update last active time
   */
  async updateLastActive(id: string): Promise<void> {
    await this.pool.query(
      `UPDATE sessions SET last_active_at = NOW() WHERE id = $1`,
      [id]
    );
  }

  /**
   * Revoke a session
   */
  async revoke(
    id: string,
    reason: string,
    revokedBy?: string,
    ipAddress?: string,
    userAgent?: string
  ): Promise<boolean> {
    const result = await this.pool.query(
      `UPDATE sessions
       SET revoked = TRUE, revoked_at = NOW(), revoked_reason = $2, revoked_by = $3
       WHERE id = $1 AND revoked = FALSE
       RETURNING user_id`,
      [id, reason, revokedBy || null]
    );

    if (result.rows[0]) {
      await this.logAudit(result.rows[0].user_id, 'SESSION_REVOKED', ipAddress, userAgent, {
        sessionId: id,
        reason,
        revokedBy,
      });
      return true;
    }

    return false;
  }

  /**
   * Revoke all sessions for a user
   */
  async revokeAllForUser(
    userId: string,
    reason: string,
    revokedBy?: string,
    excludeSessionId?: string
  ): Promise<number> {
    const result = await this.pool.query(
      `SELECT revoke_user_sessions($1, $2, $3, $4) as count`,
      [userId, reason, revokedBy || null, excludeSessionId || null]
    );

    return result.rows[0]?.count || 0;
  }

  /**
   * Get session count for a user
   */
  async getActiveCount(userId: string): Promise<number> {
    const result = await this.pool.query(
      `SELECT COUNT(*) as count FROM sessions
       WHERE user_id = $1 AND revoked = FALSE AND expires_at > NOW()`,
      [userId]
    );

    return parseInt(result.rows[0].count, 10);
  }

  /**
   * Log audit event
   */
  private async logAudit(
    userId: string,
    action: string,
    ipAddress?: string,
    userAgent?: string,
    details?: Record<string, any>
  ): Promise<void> {
    await this.pool.query(
      `INSERT INTO session_audit_log (user_id, action, ip_address, user_agent, details)
       VALUES ($1, $2, $3::inet, $4, $5)`,
      [userId, action, ipAddress || null, userAgent || null, JSON.stringify(details || {})]
    );
  }

  /**
   * Get audit log for a user
   */
  async getAuditLog(
    userId: string,
    limit: number = 100
  ): Promise<Array<{ action: string; createdAt: Date; details: any }>> {
    const result = await this.pool.query(
      `SELECT action, created_at, details FROM session_audit_log
       WHERE user_id = $1
       ORDER BY created_at DESC
       LIMIT $2`,
      [userId, limit]
    );

    return result.rows.map(row => ({
      action: row.action,
      createdAt: row.created_at,
      details: row.details,
    }));
  }

  /**
   * Cleanup expired sessions
   */
  async cleanup(): Promise<number> {
    const result = await this.pool.query(`SELECT cleanup_expired_sessions() as count`);
    return result.rows[0]?.count || 0;
  }

  /**
   * Map database row to session object
   */
  private mapRow(row: any): DbSession {
    return {
      id: row.id,
      userId: row.user_id,
      tokenHash: row.token_hash,
      deviceInfo: row.device_info,
      ipAddress: row.ip_address,
      userAgent: row.user_agent,
      createdAt: row.created_at,
      lastActiveAt: row.last_active_at,
      expiresAt: row.expires_at,
      revoked: row.revoked,
      revokedAt: row.revoked_at,
      revokedBy: row.revoked_by,
      revokedReason: row.revoked_reason,
    };
  }

  /**
   * Close connection pool
   */
  async close(): Promise<void> {
    await this.pool.end();
  }
}
```

---

## NextAuth.js Session Revocation

### Update NextAuth Configuration

Update `ui/lib/auth-config.ts`:

```typescript
/**
 * PULSE NextAuth Configuration with Session Revocation
 */

import { NextAuthOptions } from 'next-auth';
import AzureADProvider from 'next-auth/providers/azure-ad';
import { getSessionStore } from './session-store';
import { v4 as uuidv4 } from 'uuid';

// Extend session type
declare module 'next-auth' {
  interface Session {
    sessionId: string;
    user: {
      id: string;
      email: string;
      name: string;
    };
  }
}

declare module 'next-auth/jwt' {
  interface JWT {
    sessionId: string;
    userId: string;
  }
}

export const authOptions: NextAuthOptions = {
  providers: [
    AzureADProvider({
      clientId: process.env.AZURE_AD_CLIENT_ID!,
      clientSecret: process.env.AZURE_AD_CLIENT_SECRET!,
      tenantId: process.env.AZURE_AD_TENANT_ID!,
    }),
  ],

  session: {
    strategy: 'jwt',
    maxAge: 7 * 24 * 60 * 60, // 7 days
  },

  callbacks: {
    async signIn({ user, account }) {
      // Create session in store
      try {
        const sessionStore = getSessionStore();
        const sessionId = uuidv4();

        await sessionStore.createSession({
          userId: user.id!,
          email: user.email!,
          ipAddress: 'unknown', // Will be set in middleware
          userAgent: 'unknown', // Will be set in middleware
          expiresInSeconds: 7 * 24 * 60 * 60,
        });

        return true;
      } catch (error) {
        console.error('Failed to create session:', error);
        return true; // Still allow login, but without revocation support
      }
    },

    async jwt({ token, user, trigger }) {
      if (user) {
        // Initial sign in
        token.userId = user.id!;
        token.sessionId = uuidv4();
      }

      // Check if session is revoked
      if (token.sessionId) {
        try {
          const sessionStore = getSessionStore();
          const isRevoked = await sessionStore.isSessionRevoked(token.sessionId);

          if (isRevoked) {
            // Return empty token to force re-authentication
            return {} as any;
          }
        } catch (error) {
          console.error('Failed to check session revocation:', error);
        }
      }

      return token;
    },

    async session({ session, token }) {
      if (token.userId) {
        session.user.id = token.userId;
        session.sessionId = token.sessionId;
      }
      return session;
    },
  },

  events: {
    async signOut({ token }) {
      // Revoke session on logout
      if (token?.sessionId) {
        try {
          const sessionStore = getSessionStore();
          await sessionStore.revokeSession(token.sessionId, 'User logout');
        } catch (error) {
          console.error('Failed to revoke session:', error);
        }
      }
    },
  },

  pages: {
    signIn: '/auth/signin',
    signOut: '/auth/signout',
    error: '/auth/error',
  },
};
```

### Session Validation Middleware

Create `ui/middleware.ts`:

```typescript
/**
 * PULSE Middleware with Session Validation
 */

import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';
import { getToken } from 'next-auth/jwt';

// Paths that don't require authentication
const publicPaths = [
  '/auth',
  '/api/auth',
  '/health',
  '/_next',
  '/favicon.ico',
];

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Skip public paths
  if (publicPaths.some(path => pathname.startsWith(path))) {
    return NextResponse.next();
  }

  // Get JWT token
  const token = await getToken({
    req: request,
    secret: process.env.NEXTAUTH_SECRET,
  });

  // No token - redirect to signin
  if (!token) {
    const signInUrl = new URL('/auth/signin', request.url);
    signInUrl.searchParams.set('callbackUrl', pathname);
    return NextResponse.redirect(signInUrl);
  }

  // Check for empty token (session revoked)
  if (!token.sessionId || !token.userId) {
    const signInUrl = new URL('/auth/signin', request.url);
    signInUrl.searchParams.set('error', 'SessionRevoked');
    return NextResponse.redirect(signInUrl);
  }

  // Add session info to headers for downstream use
  const response = NextResponse.next();
  response.headers.set('x-user-id', token.userId as string);
  response.headers.set('x-session-id', token.sessionId as string);

  return response;
}

export const config = {
  matcher: [
    '/((?!_next/static|_next/image|favicon.ico).*)',
  ],
};
```

---

## Forced Logout Implementation

### Session Management API

Create `ui/app/api/sessions/route.ts`:

```typescript
/**
 * PULSE Sessions API
 * Manage user sessions
 */

import { NextRequest, NextResponse } from 'next/server';
import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth-config';
import { getSessionStore } from '@/lib/session-store';

// GET /api/sessions - Get current user's sessions
export async function GET(request: NextRequest) {
  const session = await getServerSession(authOptions);

  if (!session?.user?.id) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  try {
    const sessionStore = getSessionStore();
    const sessions = await sessionStore.getUserSessions(session.user.id);

    // Mark current session
    const sessionsWithCurrent = sessions.map(s => ({
      ...s,
      isCurrent: s.id === session.sessionId,
    }));

    return NextResponse.json({ sessions: sessionsWithCurrent });
  } catch (error) {
    console.error('Failed to get sessions:', error);
    return NextResponse.json(
      { error: 'Failed to retrieve sessions' },
      { status: 500 }
    );
  }
}

// DELETE /api/sessions - Revoke sessions
export async function DELETE(request: NextRequest) {
  const session = await getServerSession(authOptions);

  if (!session?.user?.id) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  try {
    const body = await request.json();
    const { sessionId, all } = body;

    const sessionStore = getSessionStore();

    if (all) {
      // Revoke all sessions except current
      const count = await sessionStore.revokeAllUserSessions(
        session.user.id,
        'User requested logout from all devices',
        session.sessionId
      );

      return NextResponse.json({
        success: true,
        message: `Revoked ${count} sessions`,
        revokedCount: count,
      });
    }

    if (sessionId) {
      // Prevent revoking current session through this endpoint
      if (sessionId === session.sessionId) {
        return NextResponse.json(
          { error: 'Cannot revoke current session. Use logout instead.' },
          { status: 400 }
        );
      }

      // Verify session belongs to user
      const targetSession = await sessionStore.getSession(sessionId);
      if (!targetSession || targetSession.userId !== session.user.id) {
        return NextResponse.json({ error: 'Session not found' }, { status: 404 });
      }

      await sessionStore.revokeSession(sessionId, 'User revoked session');

      return NextResponse.json({
        success: true,
        message: 'Session revoked',
      });
    }

    return NextResponse.json(
      { error: 'sessionId or all=true required' },
      { status: 400 }
    );
  } catch (error) {
    console.error('Failed to revoke session:', error);
    return NextResponse.json(
      { error: 'Failed to revoke session' },
      { status: 500 }
    );
  }
}
```

### Session Revoked Page

Create `ui/app/auth/session-revoked/page.tsx`:

```tsx
/**
 * Session Revoked Page
 */

'use client';

import { useEffect } from 'react';
import { signOut } from 'next-auth/react';
import Link from 'next/link';

export default function SessionRevokedPage() {
  useEffect(() => {
    // Clear local session state
    signOut({ redirect: false });
  }, []);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="max-w-md w-full space-y-8 p-8 bg-white rounded-lg shadow">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-gray-900">
            Session Ended
          </h1>
          <p className="mt-4 text-gray-600">
            Your session has been ended. This may have happened because:
          </p>
          <ul className="mt-4 text-left text-gray-600 list-disc list-inside">
            <li>You signed out from another device</li>
            <li>Your password was changed</li>
            <li>An administrator ended your session</li>
            <li>Your session expired</li>
          </ul>
          <div className="mt-8">
            <Link
              href="/auth/signin"
              className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700"
            >
              Sign In Again
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
```

---

## Multi-Device Session Management

### Sessions UI Component

Create `ui/components/SessionsManager.tsx`:

```tsx
/**
 * Sessions Manager Component
 * Displays and manages active sessions
 */

'use client';

import { useState, useEffect } from 'react';
import { formatDistanceToNow } from 'date-fns';

interface Session {
  id: string;
  deviceInfo: string;
  ipAddress: string;
  lastActiveAt: string;
  createdAt: string;
  isCurrent: boolean;
}

export function SessionsManager() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [revoking, setRevoking] = useState<string | null>(null);

  useEffect(() => {
    fetchSessions();
  }, []);

  async function fetchSessions() {
    try {
      const response = await fetch('/api/sessions');
      if (!response.ok) throw new Error('Failed to fetch sessions');
      const data = await response.json();
      setSessions(data.sessions);
    } catch (err) {
      setError('Failed to load sessions');
    } finally {
      setLoading(false);
    }
  }

  async function revokeSession(sessionId: string) {
    setRevoking(sessionId);
    try {
      const response = await fetch('/api/sessions', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sessionId }),
      });

      if (!response.ok) throw new Error('Failed to revoke session');

      setSessions(sessions.filter(s => s.id !== sessionId));
    } catch (err) {
      setError('Failed to revoke session');
    } finally {
      setRevoking(null);
    }
  }

  async function revokeAllSessions() {
    if (!confirm('This will sign you out from all other devices. Continue?')) {
      return;
    }

    setRevoking('all');
    try {
      const response = await fetch('/api/sessions', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ all: true }),
      });

      if (!response.ok) throw new Error('Failed to revoke sessions');

      const data = await response.json();
      alert(`Signed out from ${data.revokedCount} devices`);
      fetchSessions();
    } catch (err) {
      setError('Failed to revoke sessions');
    } finally {
      setRevoking(null);
    }
  }

  if (loading) {
    return <div className="animate-pulse">Loading sessions...</div>;
  }

  if (error) {
    return <div className="text-red-600">{error}</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-xl font-semibold">Active Sessions</h2>
        {sessions.length > 1 && (
          <button
            onClick={revokeAllSessions}
            disabled={revoking === 'all'}
            className="px-4 py-2 text-sm text-red-600 border border-red-600 rounded hover:bg-red-50 disabled:opacity-50"
          >
            {revoking === 'all' ? 'Signing out...' : 'Sign out all other devices'}
          </button>
        )}
      </div>

      <div className="space-y-4">
        {sessions.map(session => (
          <div
            key={session.id}
            className={`p-4 border rounded-lg ${
              session.isCurrent ? 'border-green-500 bg-green-50' : 'border-gray-200'
            }`}
          >
            <div className="flex justify-between items-start">
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-medium">{session.deviceInfo}</span>
                  {session.isCurrent && (
                    <span className="px-2 py-1 text-xs bg-green-500 text-white rounded">
                      Current Session
                    </span>
                  )}
                </div>
                <div className="text-sm text-gray-500 mt-1">
                  IP: {session.ipAddress}
                </div>
                <div className="text-sm text-gray-500">
                  Last active: {formatDistanceToNow(new Date(session.lastActiveAt), { addSuffix: true })}
                </div>
                <div className="text-sm text-gray-500">
                  Signed in: {formatDistanceToNow(new Date(session.createdAt), { addSuffix: true })}
                </div>
              </div>

              {!session.isCurrent && (
                <button
                  onClick={() => revokeSession(session.id)}
                  disabled={revoking === session.id}
                  className="px-3 py-1 text-sm text-red-600 border border-red-600 rounded hover:bg-red-50 disabled:opacity-50"
                >
                  {revoking === session.id ? 'Revoking...' : 'Revoke'}
                </button>
              )}
            </div>
          </div>
        ))}
      </div>

      {sessions.length === 0 && (
        <div className="text-gray-500 text-center py-8">
          No active sessions found
        </div>
      )}
    </div>
  );
}
```

---

## Admin Controls

### Admin Session Management API

Create `ui/app/api/admin/sessions/route.ts`:

```typescript
/**
 * Admin Sessions API
 * Admin-level session management
 */

import { NextRequest, NextResponse } from 'next/server';
import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth-config';
import { getSessionStore } from '@/lib/session-store';
import { logSecurityEvent } from '@/lib/security-logger';

// Check if user is admin
async function isAdmin(session: any): Promise<boolean> {
  // Implement your admin check logic
  // Could check database roles, Azure AD groups, etc.
  return session?.user?.email?.endsWith('@yourdomain.com') || false;
}

// GET /api/admin/sessions?userId=xxx - Get sessions for a user
export async function GET(request: NextRequest) {
  const session = await getServerSession(authOptions);

  if (!session?.user?.id || !(await isAdmin(session))) {
    return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
  }

  const userId = request.nextUrl.searchParams.get('userId');
  if (!userId) {
    return NextResponse.json({ error: 'userId required' }, { status: 400 });
  }

  try {
    const sessionStore = getSessionStore();
    const sessions = await sessionStore.getUserSessions(userId);

    await logSecurityEvent({
      type: 'ADMIN_VIEW_SESSIONS',
      clientId: session.user.id,
      path: request.nextUrl.pathname,
      timestamp: new Date().toISOString(),
      details: { targetUserId: userId },
    });

    return NextResponse.json({ sessions });
  } catch (error) {
    console.error('Failed to get user sessions:', error);
    return NextResponse.json(
      { error: 'Failed to retrieve sessions' },
      { status: 500 }
    );
  }
}

// DELETE /api/admin/sessions - Revoke sessions for a user
export async function DELETE(request: NextRequest) {
  const session = await getServerSession(authOptions);

  if (!session?.user?.id || !(await isAdmin(session))) {
    return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
  }

  try {
    const body = await request.json();
    const { userId, sessionId, all, reason } = body;

    if (!userId) {
      return NextResponse.json({ error: 'userId required' }, { status: 400 });
    }

    const sessionStore = getSessionStore();
    const revokeReason = reason || `Admin action by ${session.user.email}`;

    if (all) {
      const count = await sessionStore.revokeAllUserSessions(userId, revokeReason);

      await logSecurityEvent({
        type: 'ADMIN_REVOKE_ALL_SESSIONS',
        clientId: session.user.id,
        path: request.nextUrl.pathname,
        timestamp: new Date().toISOString(),
        details: { targetUserId: userId, revokedCount: count, reason: revokeReason },
      });

      return NextResponse.json({
        success: true,
        message: `Revoked ${count} sessions for user`,
        revokedCount: count,
      });
    }

    if (sessionId) {
      await sessionStore.revokeSession(sessionId, revokeReason);

      await logSecurityEvent({
        type: 'ADMIN_REVOKE_SESSION',
        clientId: session.user.id,
        path: request.nextUrl.pathname,
        timestamp: new Date().toISOString(),
        details: { targetUserId: userId, sessionId, reason: revokeReason },
      });

      return NextResponse.json({
        success: true,
        message: 'Session revoked',
      });
    }

    return NextResponse.json(
      { error: 'sessionId or all=true required' },
      { status: 400 }
    );
  } catch (error) {
    console.error('Failed to revoke sessions:', error);
    return NextResponse.json(
      { error: 'Failed to revoke sessions' },
      { status: 500 }
    );
  }
}
```

---

## Monitoring and Auditing

### Session Event Logging

```typescript
// Add to ui/lib/security-logger.ts

export interface SessionEvent {
  type:
    | 'SESSION_CREATED'
    | 'SESSION_VALIDATED'
    | 'SESSION_REVOKED'
    | 'SESSION_EXPIRED'
    | 'ADMIN_REVOKE_SESSION'
    | 'ADMIN_REVOKE_ALL_SESSIONS'
    | 'FORCED_LOGOUT';
  userId: string;
  sessionId?: string;
  ipAddress?: string;
  userAgent?: string;
  reason?: string;
  adminId?: string;
}

export async function logSessionEvent(event: SessionEvent): Promise<void> {
  await logSecurityEvent({
    type: event.type,
    clientId: event.userId,
    path: '/session',
    timestamp: new Date().toISOString(),
    userId: event.userId,
    sessionId: event.sessionId,
    details: {
      ipAddress: event.ipAddress,
      userAgent: event.userAgent,
      reason: event.reason,
      adminId: event.adminId,
    },
  });
}
```

### Monitoring Queries

Create `infra/monitoring/session-queries.kql`:

```kql
// Session Management Monitoring Queries

// 1. Session activity over time
customEvents
| where timestamp > ago(24h)
| where name in ("SESSION_CREATED", "SESSION_REVOKED", "SESSION_EXPIRED")
| summarize count() by bin(timestamp, 1h), name
| render timechart

// 2. Active sessions by user
customEvents
| where timestamp > ago(24h)
| where name == "SESSION_CREATED"
| summarize sessions = count() by userId = tostring(customDimensions.userId)
| order by sessions desc
| take 20

// 3. Session revocations
customEvents
| where timestamp > ago(7d)
| where name in ("SESSION_REVOKED", "ADMIN_REVOKE_SESSION", "ADMIN_REVOKE_ALL_SESSIONS")
| project
    timestamp,
    userId = tostring(customDimensions.userId),
    reason = tostring(customDimensions.reason),
    adminId = tostring(customDimensions.adminId)
| order by timestamp desc

// 4. Forced logouts
customEvents
| where timestamp > ago(7d)
| where name == "FORCED_LOGOUT"
| summarize count() by bin(timestamp, 1d)
| render columnchart

// 5. Session duration analysis
customEvents
| where timestamp > ago(7d)
| where name == "SESSION_REVOKED"
| extend
    createdAt = todatetime(customDimensions.createdAt),
    revokedAt = timestamp
| extend duration_hours = datetime_diff('hour', revokedAt, createdAt)
| summarize
    avg_duration = avg(duration_hours),
    max_duration = max(duration_hours),
    min_duration = min(duration_hours)
    by bin(timestamp, 1d)
```

---

## Testing and Validation

### Session Test Suite

Create `ui/__tests__/session-store.test.ts`:

```typescript
import { SessionStore } from '../lib/session-store';

// Mock Redis for testing
jest.mock('ioredis', () => {
  const mockData = new Map();
  return jest.fn().mockImplementation(() => ({
    set: jest.fn((key, value, ...args) => {
      mockData.set(key, value);
      return Promise.resolve('OK');
    }),
    get: jest.fn((key) => Promise.resolve(mockData.get(key))),
    del: jest.fn((key) => {
      mockData.delete(key);
      return Promise.resolve(1);
    }),
    exists: jest.fn((key) => Promise.resolve(mockData.has(key) ? 1 : 0)),
    sadd: jest.fn(() => Promise.resolve(1)),
    smembers: jest.fn(() => Promise.resolve([])),
    srem: jest.fn(() => Promise.resolve(1)),
    expire: jest.fn(() => Promise.resolve(1)),
    pipeline: jest.fn(() => ({
      set: jest.fn().mockReturnThis(),
      sadd: jest.fn().mockReturnThis(),
      expire: jest.fn().mockReturnThis(),
      exec: jest.fn(() => Promise.resolve([])),
    })),
    quit: jest.fn(() => Promise.resolve()),
  }));
});

describe('SessionStore', () => {
  let store: SessionStore;

  beforeEach(() => {
    store = new SessionStore('redis://localhost:6379');
  });

  afterEach(async () => {
    await store.close();
  });

  describe('createSession', () => {
    it('should create a new session', async () => {
      const session = await store.createSession({
        userId: 'user-123',
        email: 'test@example.com',
        ipAddress: '192.168.1.1',
        userAgent: 'Mozilla/5.0',
      });

      expect(session.id).toBeDefined();
      expect(session.userId).toBe('user-123');
      expect(session.email).toBe('test@example.com');
      expect(session.revoked).toBe(false);
    });
  });

  describe('revokeSession', () => {
    it('should revoke an existing session', async () => {
      const session = await store.createSession({
        userId: 'user-123',
        email: 'test@example.com',
        ipAddress: '192.168.1.1',
        userAgent: 'Mozilla/5.0',
      });

      const revoked = await store.revokeSession(session.id, 'Test revocation');
      expect(revoked).toBe(true);
    });
  });

  describe('isSessionRevoked', () => {
    it('should return true for revoked sessions', async () => {
      const session = await store.createSession({
        userId: 'user-123',
        email: 'test@example.com',
        ipAddress: '192.168.1.1',
        userAgent: 'Mozilla/5.0',
      });

      await store.revokeSession(session.id, 'Test');

      const isRevoked = await store.isSessionRevoked(session.id);
      expect(isRevoked).toBe(true);
    });
  });
});
```

### Integration Test Script

Create `scripts/test-session-revocation.sh`:

```bash
#!/bin/bash
# PULSE Session Revocation Integration Tests

set -e

API_URL="${1:-http://localhost:3000}"
echo "Testing session revocation at: $API_URL"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

# Get a test session token (you'd need to implement this)
echo "1. Testing session creation..."
# This would require actual authentication flow

echo "2. Testing session listing..."
response=$(curl -s "$API_URL/api/sessions" -H "Authorization: Bearer $TOKEN")
echo "Response: $response"

echo "3. Testing session revocation..."
# Test revoking a specific session

echo "4. Testing 'revoke all' functionality..."
# Test revoking all sessions

echo "5. Testing access after revocation..."
# Verify that revoked session can't access protected resources

echo ""
echo "=== Session Revocation Tests Complete ==="
```

---

## Migration Checklist

### Phase 1: Infrastructure

- [ ] Deploy Azure Cache for Redis
- [ ] Create PostgreSQL sessions table
- [ ] Configure Redis connection strings
- [ ] Update Terraform with new resources

### Phase 2: Backend Implementation

- [ ] Create `ui/lib/session-store.ts`
- [ ] Create `ui/lib/session-repository.ts`
- [ ] Update NextAuth configuration
- [ ] Create session validation middleware
- [ ] Create sessions API endpoints

### Phase 3: Admin Features

- [ ] Create admin sessions API
- [ ] Implement admin UI components
- [ ] Add security event logging
- [ ] Configure admin role checks

### Phase 4: User Features

- [ ] Create SessionsManager component
- [ ] Add sessions page to settings
- [ ] Implement revoke functionality
- [ ] Add session revoked page

### Phase 5: Monitoring

- [ ] Deploy Log Analytics queries
- [ ] Create monitoring dashboard
- [ ] Configure security alerts
- [ ] Document incident procedures

### Phase 6: Testing

- [ ] Run unit tests
- [ ] Execute integration tests
- [ ] Test revocation flows
- [ ] Load test Redis performance

---

## Best Practices Summary

1. **Hybrid Storage**: Use Redis for fast lookup, DB for persistence
2. **Short Token Lifetime**: Use short-lived JWTs with refresh tokens
3. **Immediate Revocation**: Check blacklist on every request
4. **Audit Everything**: Log all session events
5. **User Visibility**: Show users their active sessions
6. **Admin Controls**: Provide admin session management
7. **Graceful Handling**: Show clear message when session revoked

---

## Related Documents

- [securedbydesign.md](securedbydesign.md) - Overall security assessment
- [secretsmanage.md](secretsmanage.md) - Secrets management
- [ratelimiting.md](ratelimiting.md) - Rate limiting implementation
