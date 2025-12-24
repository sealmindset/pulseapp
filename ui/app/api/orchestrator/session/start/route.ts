import { NextRequest } from "next/server";
import { requireAuth } from "@/lib/auth-utils";

export const runtime = "nodejs";

export async function OPTIONS() {
  return new Response(null, {
    status: 204,
    headers: {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type, Authorization",
    },
  });
}

export async function POST(req: NextRequest) {
  // Require authentication for session start
  const authResult = await requireAuth();
  if (authResult.error) {
    return authResult.error;
  }

  const base = process.env.FUNCTION_APP_BASE_URL;
  if (!base) {
    return new Response("Missing FUNCTION_APP_BASE_URL", { status: 500 });
  }

  const json = await req.json();

  // Include user info in the session request
  const enrichedJson = {
    ...json,
    userId: authResult.session.user.userId || authResult.session.user.id,
    userEmail: authResult.session.user.email,
    userName: authResult.session.user.name,
  };

  const target = `${base.replace(/\/$/, "")}/session/start`;

  const res = await fetch(target, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(enrichedJson),
  });

  const body = await res.text();
  const headers = new Headers({ "Content-Type": res.headers.get("Content-Type") || "application/json" });
  headers.set("Access-Control-Allow-Origin", "*");

  return new Response(body, { status: res.status, headers });
}
