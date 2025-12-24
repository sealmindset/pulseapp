// =============================================================================
// Check User Access API
// Called during SSO sign-in to verify user authorization
// =============================================================================

import { NextRequest, NextResponse } from "next/server";
import { checkUserAccess } from "@/lib/auth-db";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { email, name, entraObjectId } = body;

    if (!email) {
      return NextResponse.json({ error: "Email required" }, { status: 400 });
    }

    const result = await checkUserAccess(email, name || email.split("@")[0], entraObjectId);

    if (result.allowed) {
      return NextResponse.json({
        allowed: true,
        status: result.status,
        user: result.user,
      });
    }

    if (result.status === "pending") {
      return NextResponse.json(
        {
          allowed: false,
          status: "pending",
          error: "PendingApproval",
          message: result.reason,
        },
        { status: 403 }
      );
    }

    return NextResponse.json(
      {
        allowed: false,
        error: result.reason || "AccessDenied",
      },
      { status: 403 }
    );
  } catch (error) {
    console.error("Error checking user:", error);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}
