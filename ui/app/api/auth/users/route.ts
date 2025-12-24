// =============================================================================
// User Management API Routes
// Protected - requires admin role
// =============================================================================

import { NextRequest, NextResponse } from "next/server";
import {
  getUsers,
  createUser,
  updateUser,
  approveUser,
  rejectUser,
  getPendingApprovals,
} from "@/lib/auth-db";
import { requireAdmin } from "@/lib/auth-utils";
import type { UserRole, UserStatus } from "@/types/auth";

// GET /api/auth/users - List all users
export async function GET(request: NextRequest) {
  // Require admin authentication
  const authResult = await requireAdmin();
  if (authResult.error) {
    return authResult.error;
  }

  try {
    const { searchParams } = new URL(request.url);
    const status = searchParams.get("status") as UserStatus | null;
    const role = searchParams.get("role") as UserRole | null;
    const pending = searchParams.get("pending") === "true";

    if (pending) {
      const pendingUsers = await getPendingApprovals();
      return NextResponse.json(pendingUsers);
    }

    let users = await getUsers();

    if (status) {
      users = users.filter((u) => u.status === status);
    }
    if (role) {
      users = users.filter((u) => u.role === role);
    }

    return NextResponse.json(users);
  } catch (error) {
    console.error("Error fetching users:", error);
    return NextResponse.json(
      { error: "Failed to fetch users" },
      { status: 500 }
    );
  }
}

// POST /api/auth/users - Create a new user
export async function POST(request: NextRequest) {
  // Require admin authentication
  const authResult = await requireAdmin();
  if (authResult.error) {
    return authResult.error;
  }

  try {
    const body = await request.json();
    const { email, name, role, status, authMethod } = body;

    if (!email || !name) {
      return NextResponse.json(
        { error: "Email and name are required" },
        { status: 400 }
      );
    }

    const user = await createUser({
      email,
      name,
      role: role || "trainee",
      status: status || "pending",
      authMethod: authMethod || "sso",
    });

    return NextResponse.json(user, { status: 201 });
  } catch (error) {
    console.error("Error creating user:", error);
    return NextResponse.json(
      { error: "Failed to create user" },
      { status: 500 }
    );
  }
}

// PATCH /api/auth/users - Bulk operations
export async function PATCH(request: NextRequest) {
  // Require admin authentication
  const authResult = await requireAdmin();
  if (authResult.error) {
    return authResult.error;
  }

  try {
    const body = await request.json();
    const { action, userIds } = body;

    if (!action || !userIds || !Array.isArray(userIds)) {
      return NextResponse.json(
        { error: "Action and userIds array required" },
        { status: 400 }
      );
    }

    const results = [];
    for (const userId of userIds) {
      try {
        if (action === "approve") {
          results.push(await approveUser(userId));
        } else if (action === "reject") {
          await rejectUser(userId);
          results.push({ id: userId, status: "rejected" });
        } else if (action === "disable") {
          results.push(await updateUser(userId, { status: "disabled" }));
        } else if (action === "enable") {
          results.push(await updateUser(userId, { status: "active" }));
        }
      } catch (error) {
        results.push({ id: userId, error: "Failed to process" });
      }
    }

    return NextResponse.json({ results });
  } catch (error) {
    console.error("Error in bulk operation:", error);
    return NextResponse.json(
      { error: "Failed to process bulk operation" },
      { status: 500 }
    );
  }
}
