// =============================================================================
// PULSE Authentication Utilities
// Server-side helpers for API route protection
// =============================================================================

import { getServerSession } from "next-auth";
import { NextResponse } from "next/server";
import { authOptions } from "./auth-config";
import type { UserRole } from "@/types/auth";

// Extended session user type
interface SessionUser {
  id?: string;
  email?: string;
  name?: string;
  role?: UserRole;
  status?: string;
  userId?: string;
}

interface AuthSession {
  user: SessionUser;
}

// Roles that have admin access
const ADMIN_ROLES: UserRole[] = ["super_admin", "admin", "manager"];

/**
 * Get the current session for API routes
 * Returns null if not authenticated
 */
export async function getApiSession(): Promise<AuthSession | null> {
  const session = await getServerSession(authOptions);
  return session as AuthSession | null;
}

/**
 * Require authentication for an API route
 * Returns an error response if not authenticated
 */
export async function requireAuth(): Promise<
  | { session: AuthSession; error: null }
  | { session: null; error: NextResponse }
> {
  const session = await getApiSession();

  if (!session?.user) {
    return {
      session: null,
      error: NextResponse.json(
        { error: "Unauthorized", message: "Authentication required" },
        { status: 401 }
      ),
    };
  }

  // Check if user is still active
  if (session.user.status && session.user.status !== "active") {
    return {
      session: null,
      error: NextResponse.json(
        { error: "Forbidden", message: "Account is not active" },
        { status: 403 }
      ),
    };
  }

  return { session, error: null };
}

/**
 * Require admin role for an API route
 * Returns an error response if not authenticated or not an admin
 */
export async function requireAdmin(): Promise<
  | { session: AuthSession; error: null }
  | { session: null; error: NextResponse }
> {
  const authResult = await requireAuth();

  if (authResult.error) {
    return authResult;
  }

  const { session } = authResult;
  const userRole = session.user.role as UserRole | undefined;

  if (!userRole || !ADMIN_ROLES.includes(userRole)) {
    return {
      session: null,
      error: NextResponse.json(
        { error: "Forbidden", message: "Admin access required" },
        { status: 403 }
      ),
    };
  }

  return { session, error: null };
}

/**
 * Require a specific role or higher for an API route
 */
export async function requireRole(
  allowedRoles: UserRole[]
): Promise<
  | { session: AuthSession; error: null }
  | { session: null; error: NextResponse }
> {
  const authResult = await requireAuth();

  if (authResult.error) {
    return authResult;
  }

  const { session } = authResult;
  const userRole = session.user.role as UserRole | undefined;

  // Super admin always has access
  if (userRole === "super_admin") {
    return { session, error: null };
  }

  if (!userRole || !allowedRoles.includes(userRole)) {
    return {
      session: null,
      error: NextResponse.json(
        { error: "Forbidden", message: "Insufficient permissions" },
        { status: 403 }
      ),
    };
  }

  return { session, error: null };
}

/**
 * Check if the current user can access a resource
 * Used for permission-based access control
 */
export function hasPermission(
  userRole: UserRole | undefined,
  permission: string
): boolean {
  if (!userRole) return false;

  const permissionMap: Record<UserRole, string[]> = {
    super_admin: ["*"],
    admin: ["users:*", "settings:*", "content:*", "reports:view", "training:*", "ai:*"],
    manager: ["users:view", "trainees:*", "reports:*", "content:view", "training:*", "ai:*"],
    trainer: ["trainees:view", "sessions:*", "feedback:*", "reports:view", "training:*", "ai:*"],
    trainee: ["training:access", "sessions:participate", "feedback:view", "ai:*"],
  };

  const permissions = permissionMap[userRole] || [];

  // Super admin has all permissions
  if (permissions.includes("*")) return true;

  // Check specific permission
  return permissions.some((p) => {
    if (p === permission) return true;
    // Wildcard matching (e.g., "users:*" matches "users:view")
    if (p.endsWith(":*")) {
      const prefix = p.slice(0, -1);
      return permission.startsWith(prefix);
    }
    return false;
  });
}

/**
 * Verify CSRF token for mutation operations
 * NextAuth handles this automatically for its routes, but we can add extra protection
 */
export function verifyCsrf(request: Request): boolean {
  // For same-origin requests, check the Origin or Referer header
  const origin = request.headers.get("origin");
  const referer = request.headers.get("referer");
  const host = request.headers.get("host");

  // API calls should come from the same origin
  if (origin) {
    try {
      const originUrl = new URL(origin);
      if (host && originUrl.host !== host) {
        return false;
      }
    } catch {
      return false;
    }
  } else if (referer) {
    try {
      const refererUrl = new URL(referer);
      if (host && refererUrl.host !== host) {
        return false;
      }
    } catch {
      return false;
    }
  }

  return true;
}
