// =============================================================================
// Individual User API Routes
// Protected - requires admin role
// =============================================================================

import { NextRequest, NextResponse } from "next/server";
import { getUsers, updateUser, deleteUser, approveUser, rejectUser } from "@/lib/auth-db";
import { requireAdmin } from "@/lib/auth-utils";

// GET /api/auth/users/[id] - Get a single user
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  // Require admin authentication
  const authResult = await requireAdmin();
  if (authResult.error) {
    return authResult.error;
  }

  try {
    const { id } = await params;
    const users = await getUsers();
    const user = users.find((u) => u.id === id);

    if (!user) {
      return NextResponse.json({ error: "User not found" }, { status: 404 });
    }

    return NextResponse.json(user);
  } catch (error) {
    console.error("Error fetching user:", error);
    return NextResponse.json({ error: "Failed to fetch user" }, { status: 500 });
  }
}

// PATCH /api/auth/users/[id] - Update a user
export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  // Require admin authentication
  const authResult = await requireAdmin();
  if (authResult.error) {
    return authResult.error;
  }

  try {
    const { id } = await params;
    const body = await request.json();

    // Handle special actions
    if (body.action === "approve") {
      const user = await approveUser(id);
      return NextResponse.json(user);
    }
    if (body.action === "reject") {
      await rejectUser(id);
      return NextResponse.json({ success: true });
    }

    // Regular update
    const user = await updateUser(id, body);
    return NextResponse.json(user);
  } catch (error) {
    console.error("Error updating user:", error);
    return NextResponse.json({ error: "Failed to update user" }, { status: 500 });
  }
}

// DELETE /api/auth/users/[id] - Delete a user
export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  // Require admin authentication
  const authResult = await requireAdmin();
  if (authResult.error) {
    return authResult.error;
  }

  try {
    const { id } = await params;

    // Prevent deletion of demo user
    if (id === "user-demo" || id === "demo-user") {
      return NextResponse.json(
        { error: "Cannot delete demo user" },
        { status: 403 }
      );
    }

    await deleteUser(id);
    return NextResponse.json({ success: true });
  } catch (error) {
    console.error("Error deleting user:", error);
    return NextResponse.json({ error: "Failed to delete user" }, { status: 500 });
  }
}
