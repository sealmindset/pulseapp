// =============================================================================
// OIDC Configuration API - Returns OIDC config for admin display
// =============================================================================

import { NextResponse } from "next/server";

// Force dynamic rendering to read env vars at runtime
export const dynamic = "force-dynamic";

export async function GET() {
  // Read environment variables at runtime
  const clientId = process.env.AZURE_AD_CLIENT_ID || "";
  const tenantId = process.env.AZURE_AD_TENANT_ID || "";
  const clientSecret = process.env.AZURE_AD_CLIENT_SECRET || "";
  const authMode = process.env.AUTH_MODE || "demo";

  const isConfigured = Boolean(clientId && clientSecret && tenantId);

  return NextResponse.json({
    clientId: clientId ? `${clientId.slice(0, 8)}...` : "Not configured",
    tenantId: tenantId || "Not configured",
    issuer: tenantId
      ? `https://login.microsoftonline.com/${tenantId}/v2.0`
      : "Not configured",
    authorizationUrl: tenantId
      ? `https://login.microsoftonline.com/${tenantId}/oauth2/v2.0/authorize`
      : "Not configured",
    tokenUrl: tenantId
      ? `https://login.microsoftonline.com/${tenantId}/oauth2/v2.0/token`
      : "Not configured",
    isConfigured,
    mode: authMode,
  });
}
