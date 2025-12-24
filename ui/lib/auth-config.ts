// =============================================================================
// PULSE Authentication Configuration
// =============================================================================

import type { AuthOptions } from "next-auth";
import AzureADProvider from "next-auth/providers/azure-ad";

// Environment variables
const AZURE_AD_CLIENT_ID = process.env.AZURE_AD_CLIENT_ID || "";
const AZURE_AD_CLIENT_SECRET = process.env.AZURE_AD_CLIENT_SECRET || "";
const AZURE_AD_TENANT_ID = process.env.AZURE_AD_TENANT_ID || "";
const NEXTAUTH_SECRET = process.env.NEXTAUTH_SECRET || "pulse-dev-secret-change-in-production";
const AUTH_MODE = process.env.AUTH_MODE || "demo";

// Check if SSO is configured
export const isOIDCConfigured = Boolean(
  AZURE_AD_CLIENT_ID && AZURE_AD_CLIENT_SECRET && AZURE_AD_TENANT_ID
);

export const isSSOEnabled = AUTH_MODE === "sso" && isOIDCConfigured;
export const isDemoMode = AUTH_MODE === "demo" || !isOIDCConfigured;

// NextAuth configuration
export const authOptions: AuthOptions = {
  providers: isOIDCConfigured
    ? [
        AzureADProvider({
          clientId: AZURE_AD_CLIENT_ID,
          clientSecret: AZURE_AD_CLIENT_SECRET,
          tenantId: AZURE_AD_TENANT_ID,
          authorization: {
            params: {
              scope: "openid profile email User.Read",
            },
          },
          profile(profile) {
            return {
              id: profile.oid || profile.sub,
              name: profile.name || profile.preferred_username,
              email: profile.email || profile.preferred_username,
              image: null,
              // Custom fields
              entraObjectId: profile.oid,
            };
          },
        }),
      ]
    : [],

  secret: NEXTAUTH_SECRET,

  session: {
    strategy: "jwt",
    maxAge: 8 * 60 * 60, // 8 hours (480 minutes)
  },

  pages: {
    signIn: "/",
    error: "/auth/error",
  },

  callbacks: {
    async signIn({ user, account }) {
      if (!user.email) {
        return false;
      }

      // In SSO mode, check if user exists and is approved
      if (isSSOEnabled) {
        try {
          const baseUrl = process.env.NEXTAUTH_URL || "http://localhost:3000";
          const response = await fetch(`${baseUrl}/api/auth/check-user`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              email: user.email,
              name: user.name,
              entraObjectId: account?.providerAccountId,
            }),
          });

          if (!response.ok) {
            const data = await response.json();
            // Return error page with reason
            return `/auth/error?error=${encodeURIComponent(data.error || "AccessDenied")}`;
          }

          const userData = await response.json();
          if (userData.status === "pending") {
            return "/auth/pending";
          }
          if (userData.status !== "active") {
            return "/auth/error?error=AccountDisabled";
          }
        } catch (error) {
          console.error("Error checking user:", error);
          // Allow sign-in but log the error
        }
      }

      return true;
    },

    async jwt({ token, user, account, trigger }) {
      if (user) {
        token.id = user.id;
        token.email = user.email;
        token.name = user.name;
        token.entraObjectId = (user as { entraObjectId?: string }).entraObjectId;
      }
      if (account) {
        token.accessToken = account.access_token;
        token.provider = account.provider;
      }

      // Fetch user role from database on initial sign-in or token refresh
      if ((user || trigger === "update") && token.email) {
        try {
          const baseUrl = process.env.NEXTAUTH_URL || "http://localhost:3000";
          const response = await fetch(`${baseUrl}/api/auth/check-user`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email: token.email }),
          });
          if (response.ok) {
            const userData = await response.json();
            // Role and status are nested in userData.user
            token.role = userData.user?.role || userData.role;
            token.status = userData.user?.status || userData.status;
            token.userId = userData.user?.id || userData.id;
          }
        } catch (error) {
          console.error("Error fetching user role:", error);
        }
      }

      return token;
    },

    async session({ session, token }) {
      if (session.user) {
        // Extend session.user with custom properties
        const extendedUser = session.user as {
          id?: string;
          email?: string | null;
          name?: string | null;
          image?: string | null;
          entraObjectId?: string;
          provider?: string;
          role?: string;
          status?: string;
          userId?: string;
        };
        extendedUser.id = token.id as string;
        extendedUser.email = token.email as string;
        extendedUser.name = token.name as string;
        extendedUser.entraObjectId = token.entraObjectId as string;
        extendedUser.provider = token.provider as string;
        extendedUser.role = token.role as string;
        extendedUser.status = token.status as string;
        extendedUser.userId = token.userId as string;
      }
      return session;
    },

    async redirect({ url, baseUrl }) {
      // Redirect to pre-session after successful login
      if (url.startsWith(baseUrl)) {
        return url;
      }
      return `${baseUrl}/pre-session`;
    },
  },

  events: {
    async signIn({ user }) {
      // Update last login timestamp
      if (user.email) {
        try {
          const baseUrl = process.env.NEXTAUTH_URL || "http://localhost:3000";
          await fetch(`${baseUrl}/api/auth/update-login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email: user.email }),
          });
        } catch (error) {
          console.error("Error updating last login:", error);
        }
      }
    },
  },

  debug: process.env.NODE_ENV === "development",
};

// OIDC configuration for display in admin panel (secrets redacted)
export function getOIDCDisplayConfig() {
  return {
    clientId: AZURE_AD_CLIENT_ID ? `${AZURE_AD_CLIENT_ID.slice(0, 8)}...` : "Not configured",
    tenantId: AZURE_AD_TENANT_ID || "Not configured",
    issuer: AZURE_AD_TENANT_ID
      ? `https://login.microsoftonline.com/${AZURE_AD_TENANT_ID}/v2.0`
      : "Not configured",
    authorizationUrl: AZURE_AD_TENANT_ID
      ? `https://login.microsoftonline.com/${AZURE_AD_TENANT_ID}/oauth2/v2.0/authorize`
      : "Not configured",
    tokenUrl: AZURE_AD_TENANT_ID
      ? `https://login.microsoftonline.com/${AZURE_AD_TENANT_ID}/oauth2/v2.0/token`
      : "Not configured",
    isConfigured: isOIDCConfigured,
    mode: AUTH_MODE,
  };
}
