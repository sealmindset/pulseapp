// =============================================================================
// Invitation Management API Routes
// Protected - requires admin role
// =============================================================================

import { NextRequest, NextResponse } from "next/server";
import {
  getInvitations,
  createInvitation,
  revokeInvitation,
  generateInviteUrl,
} from "@/lib/auth-db";
import { requireAdmin } from "@/lib/auth-utils";
import type { UserRole, InvitationType } from "@/types/auth";

// GET /api/auth/invitations - List all invitations
export async function GET() {
  // Require admin authentication
  const authResult = await requireAdmin();
  if (authResult.error) {
    return authResult.error;
  }

  try {
    const invitations = await getInvitations();
    return NextResponse.json(invitations);
  } catch (error) {
    console.error("Error fetching invitations:", error);
    return NextResponse.json(
      { error: "Failed to fetch invitations" },
      { status: 500 }
    );
  }
}

// POST /api/auth/invitations - Create a new invitation
export async function POST(request: NextRequest) {
  // Require admin authentication
  const authResult = await requireAdmin();
  if (authResult.error) {
    return authResult.error;
  }

  try {
    const body = await request.json();
    const {
      type,
      email,
      role,
      expiresIn, // in days
      maxUses,
      allowedDomains,
      notes,
    } = body;

    if (!type || (type === "email" && !email)) {
      return NextResponse.json(
        { error: "Type required, email required for email invitations" },
        { status: 400 }
      );
    }

    // Calculate expiration date
    const expiresAt = new Date();
    expiresAt.setDate(expiresAt.getDate() + (expiresIn || 7));

    // Get the current user's email from session
    const createdByEmail = authResult.session.user.email;

    const invitation = await createInvitation({
      type: type as InvitationType,
      email: type === "email" ? email : undefined,
      role: (role as UserRole) || "trainee",
      expiresAt: expiresAt.toISOString(),
      maxUses: maxUses || (type === "email" ? 1 : 10),
      requiresApproval: true, // Always require approval per requirements
      allowedDomains: allowedDomains || [],
      notes,
      createdByEmail,
    });

    // Generate the invite URL for link type
    const inviteUrl = generateInviteUrl(invitation.code);

    return NextResponse.json(
      {
        ...invitation,
        inviteUrl,
      },
      { status: 201 }
    );
  } catch (error) {
    console.error("Error creating invitation:", error);
    return NextResponse.json(
      { error: "Failed to create invitation" },
      { status: 500 }
    );
  }
}

// DELETE /api/auth/invitations - Revoke invitations (bulk)
export async function DELETE(request: NextRequest) {
  // Require admin authentication
  const authResult = await requireAdmin();
  if (authResult.error) {
    return authResult.error;
  }

  try {
    const body = await request.json();
    const { ids } = body;

    if (!ids || !Array.isArray(ids)) {
      return NextResponse.json(
        { error: "Array of invitation IDs required" },
        { status: 400 }
      );
    }

    for (const id of ids) {
      await revokeInvitation(id);
    }

    return NextResponse.json({ success: true, revoked: ids.length });
  } catch (error) {
    console.error("Error revoking invitations:", error);
    return NextResponse.json(
      { error: "Failed to revoke invitations" },
      { status: 500 }
    );
  }
}
