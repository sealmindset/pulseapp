"use client";

import { createContext, useContext, useState, useEffect, ReactNode } from "react";
import { SessionProvider, useSession, signIn, signOut } from "next-auth/react";
import type { PulseUser, UserRole } from "@/types/auth";
import { getUserByEmail, getAuthSettings } from "@/lib/auth-db";

// =============================================================================
// Types
// =============================================================================

interface AuthContextType {
  isAuthenticated: boolean;
  isLoading: boolean;
  user: PulseUser | null;
  login: (username: string, password: string) => Promise<boolean>;
  loginWithSSO: () => Promise<void>;
  logout: () => Promise<void>;
  authMode: "demo" | "sso";
  canAccess: (permission: string) => boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

// Storage keys
const AUTH_KEY = "pulse_auth";

// =============================================================================
// Auth Provider Inner (uses hooks)
// =============================================================================

function AuthProviderInner({ children }: { children: ReactNode }) {
  const { data: session, status } = useSession();
  const [user, setUser] = useState<PulseUser | null>(null);
  const [authMode, setAuthMode] = useState<"demo" | "sso">("demo");
  const [isLoading, setIsLoading] = useState(true);

  // Load auth mode and check for demo login on mount
  useEffect(() => {
    async function initialize() {
      setIsLoading(true);
      try {
        // Get auth settings
        const settings = await getAuthSettings();
        setAuthMode(settings.authMode);

        // Check for SSO session
        if (status === "authenticated" && session?.user?.email) {
          const pulseUser = await getUserByEmail(session.user.email);
          if (pulseUser && pulseUser.status === "active") {
            setUser(pulseUser);
            setIsLoading(false);
            return;
          }
        }

        // Check for demo login in localStorage
        if (typeof window !== "undefined") {
          const stored = localStorage.getItem(AUTH_KEY);
          if (stored) {
            try {
              const parsed = JSON.parse(stored);
              if (parsed.isAuthenticated && parsed.user) {
                // Validate user still exists and is active
                const pulseUser = await getUserByEmail(parsed.user.email || "demo@pulse.training");
                if (pulseUser && pulseUser.status === "active") {
                  setUser(pulseUser);
                }
              }
            } catch {
              // Invalid stored data, ignore
            }
          }
        }
      } catch (error) {
        console.error("Error initializing auth:", error);
      }
      setIsLoading(false);
    }

    if (status !== "loading") {
      initialize();
    }
  }, [session, status]);

  // Demo mode login
  const login = async (username: string, password: string): Promise<boolean> => {
    // Check if SSO mode is enabled
    if (authMode === "sso") {
      return false; // Demo login disabled in SSO mode
    }

    // Accept demo/demo credentials
    if (username === "demo" && password === "demo") {
      const demoUser = await getUserByEmail("demo@pulse.training");
      if (demoUser) {
        setUser(demoUser);
        if (typeof window !== "undefined") {
          localStorage.setItem(
            AUTH_KEY,
            JSON.stringify({ isAuthenticated: true, user: demoUser })
          );
        }
        return true;
      }
    }

    // Check if user exists with matching credentials (simplified for demo)
    const pulseUser = await getUserByEmail(username);
    if (pulseUser && pulseUser.authMethod === "local" && pulseUser.status === "active") {
      setUser(pulseUser);
      if (typeof window !== "undefined") {
        localStorage.setItem(
          AUTH_KEY,
          JSON.stringify({ isAuthenticated: true, user: pulseUser })
        );
      }
      return true;
    }

    return false;
  };

  // SSO login
  const loginWithSSO = async (): Promise<void> => {
    await signIn("azure-ad", { callbackUrl: "/pre-session" });
  };

  // Logout
  const logout = async (): Promise<void> => {
    setUser(null);
    if (typeof window !== "undefined") {
      localStorage.removeItem(AUTH_KEY);
    }

    // If SSO session exists, sign out of NextAuth too
    if (session) {
      await signOut({ callbackUrl: "/" });
    }
  };

  // Permission check
  const canAccess = (permission: string): boolean => {
    if (!user) return false;

    const role = user.role;
    const permissions = getRolePermissions(role);

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
  };

  const isAuthenticated = !!user && user.status === "active";

  return (
    <AuthContext.Provider
      value={{
        isAuthenticated,
        isLoading: isLoading || status === "loading",
        user,
        login,
        loginWithSSO,
        logout,
        authMode,
        canAccess,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

// =============================================================================
// Auth Provider Wrapper (includes SessionProvider)
// =============================================================================

export function AuthProvider({ children }: { children: ReactNode }) {
  return (
    <SessionProvider>
      <AuthProviderInner>{children}</AuthProviderInner>
    </SessionProvider>
  );
}

// =============================================================================
// Hook
// =============================================================================

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}

// =============================================================================
// Helper Functions
// =============================================================================

function getRolePermissions(role: UserRole): string[] {
  const permissionMap: Record<UserRole, string[]> = {
    super_admin: ["*"],
    admin: ["users:*", "settings:*", "content:*", "reports:view", "training:*", "ai:*"],
    manager: ["users:view", "trainees:*", "reports:*", "content:view", "training:*", "ai:*"],
    trainer: ["trainees:view", "sessions:*", "feedback:*", "reports:view", "training:*", "ai:*"],
    trainee: ["training:access", "sessions:participate", "feedback:view", "ai:*"],
  };
  return permissionMap[role] || [];
}

// =============================================================================
// Protected Route Component
// =============================================================================

export function RequireAuth({
  children,
  permission,
  fallback,
}: {
  children: ReactNode;
  permission?: string;
  fallback?: ReactNode;
}) {
  const { isAuthenticated, isLoading, canAccess } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-[50vh] flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-gray-300 border-t-black rounded-full animate-spin" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return fallback || null;
  }

  if (permission && !canAccess(permission)) {
    return (
      <div className="min-h-[50vh] flex items-center justify-center">
        <div className="text-center">
          <h2 className="text-xl font-semibold text-gray-900">Access Denied</h2>
          <p className="text-gray-600 mt-2">You don&apos;t have permission to view this page.</p>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
