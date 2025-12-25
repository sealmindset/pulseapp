import { NextRequest } from "next/server";
import { getCorsHeaders, corsOptionsResponse } from "@/lib/cors";
import { isValidUUID, validationError } from "@/lib/validation";
import { handleApiError } from "@/lib/errors";

export const runtime = "nodejs";

export async function OPTIONS(req: NextRequest) {
  return corsOptionsResponse(req);
}

export async function GET(
  req: NextRequest,
  { params }: { params: { sessionId: string } }
) {
  const origin = req.headers.get("origin");

  try {
    // Validate session ID
    if (!isValidUUID(params.sessionId)) {
      const response = validationError("Invalid session ID");
      return new Response(response.body, {
        status: response.status,
        headers: { ...Object.fromEntries(response.headers), ...getCorsHeaders(origin) },
      });
    }

    const base = process.env.FUNCTION_APP_BASE_URL;
    if (!base) {
      return new Response(JSON.stringify({ error: "Configuration error" }), {
        status: 500,
        headers: { "Content-Type": "application/json", ...getCorsHeaders(origin) },
      });
    }

    const target = `${base.replace(/\/$/, "")}/feedback/${encodeURIComponent(params.sessionId)}`;

    const res = await fetch(target, {
      method: "GET",
      headers: {
        "X-Function-Key": process.env.FUNCTION_APP_SHARED_SECRET || "",
      },
    });

    const body = await res.text();

    return new Response(body, {
      status: res.status,
      headers: {
        "Content-Type": res.headers.get("Content-Type") || "application/json",
        ...getCorsHeaders(origin),
      },
    });
  } catch (error) {
    const response = handleApiError(error, 'api/orchestrator/feedback');
    return new Response(response.body, {
      status: response.status,
      headers: { ...Object.fromEntries(response.headers), ...getCorsHeaders(origin) },
    });
  }
}
