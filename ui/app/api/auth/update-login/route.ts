// =============================================================================
// Update Last Login API
// Called after successful sign-in to update user's last login timestamp
// =============================================================================

import { NextRequest, NextResponse } from "next/server";
import { getUserByEmail, updateUser, logAuditEvent } from "@/lib/auth-db";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { email } = body;

    if (!email) {
      return NextResponse.json({ error: "Email required" }, { status: 400 });
    }

    const user = await getUserByEmail(email);
    if (!user) {
      return NextResponse.json({ error: "User not found" }, { status: 404 });
    }

    await updateUser(user.id, { lastLogin: new Date().toISOString() });
    await logAuditEvent("login", "user", user.id, null, { lastLogin: new Date().toISOString() }, email);

    return NextResponse.json({ success: true });
  } catch (error) {
    console.error("Error updating login:", error);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}
