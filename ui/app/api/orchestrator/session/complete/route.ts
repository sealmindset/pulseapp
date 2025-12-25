import { NextRequest } from "next/server";
import { getCorsHeaders, corsOptionsResponse } from "@/lib/cors";
import { validateSessionComplete, validationError } from "@/lib/validation";
import { checkRateLimit, getClientId, rateLimitResponse } from "@/lib/rate-limiter";
import { handleApiError } from "@/lib/errors";
import { auditLog, getAuditIp } from "@/lib/audit";

export const runtime = "nodejs";

export async function OPTIONS(req: NextRequest) {
  return corsOptionsResponse(req);
}

export async function POST(req: NextRequest) {
  const origin = req.headers.get("origin");
  const ip = getAuditIp(req);

  try {
    // Rate limiting
    const clientId = getClientId(req);
    const { allowed } = checkRateLimit(clientId, 'session');
    if (!allowed) {
      auditLog.rateLimited(clientId, 'session/complete', ip);
      const response = rateLimitResponse();
      return new Response(response.body, {
        status: response.status,
        headers: { ...Object.fromEntries(response.headers), ...getCorsHeaders(origin) },
      });
    }

    const json = await req.json();

    // Validate request
    const validation = validateSessionComplete(json);
    if (!validation.valid) {
      const response = validationError(validation.error!);
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

    const target = `${base.replace(/\/$/, "")}/session/complete`;

    const res = await fetch(target, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Function-Key": process.env.FUNCTION_APP_SHARED_SECRET || "",
      },
      body: JSON.stringify(json),
    });

    const body = await res.text();

    // Log session complete
    try {
      const responseData = JSON.parse(body);
      if (json.sessionId) {
        auditLog.sessionEnd(json.sessionId, ip);
      }
    } catch {
      // Ignore parse errors for audit logging
    }

    return new Response(body, {
      status: res.status,
      headers: {
        "Content-Type": res.headers.get("Content-Type") || "application/json",
        ...getCorsHeaders(origin),
      },
    });
  } catch (error) {
    auditLog.error('api/orchestrator/session/complete', error, ip);
    const response = handleApiError(error, 'api/orchestrator/session/complete');
    return new Response(response.body, {
      status: response.status,
      headers: { ...Object.fromEntries(response.headers), ...getCorsHeaders(origin) },
    });
  }
}
