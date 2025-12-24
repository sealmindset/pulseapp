// =============================================================================
// Auth Settings API - Returns auth configuration to client
// =============================================================================

import { NextResponse } from "next/server";

// Force dynamic rendering to read env vars at runtime
export const dynamic = "force-dynamic";

export async function GET() {
  // Read AUTH_MODE at runtime, not build time
  const authMode = process.env.AUTH_MODE || "demo";

  return NextResponse.json({
    authMode: authMode === "sso" ? "sso" : "demo",
    ssoEnabled: authMode === "sso",
    requireApproval: true,
    sessionTimeoutMinutes: 480,
  });
}
