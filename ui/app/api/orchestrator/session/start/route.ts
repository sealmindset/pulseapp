import { NextRequest } from "next/server";
import { requireAuth } from "@/lib/auth-utils";
import { getCorsHeaders, corsOptionsResponse } from "@/lib/cors";
import { validateSessionStart, validationError } from "@/lib/validation";
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
    // Require authentication for session start
    const authResult = await requireAuth();
    if (authResult.error) {
      return new Response(authResult.error.body, {
        status: 401,
        headers: { "Content-Type": "application/json", ...getCorsHeaders(origin) },
      });
    }

    // Rate limiting - use session limit
    const clientId = getClientId(req, authResult.session.user.userId);
    const { allowed } = checkRateLimit(clientId, 'session');
    if (!allowed) {
      auditLog.rateLimited(clientId, 'session', ip);
      const response = rateLimitResponse();
      return new Response(response.body, {
        status: response.status,
        headers: { ...Object.fromEntries(response.headers), ...getCorsHeaders(origin) },
      });
    }

    const json = await req.json();

    // Validate request
    const validation = validateSessionStart(json);
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
      headers: {
        "Content-Type": "application/json",
        "X-Function-Key": process.env.FUNCTION_APP_SHARED_SECRET || "",
      },
      body: JSON.stringify(enrichedJson),
    });

    const body = await res.text();

    // Log session start
    try {
      const responseData = JSON.parse(body);
      if (responseData.sessionId) {
        auditLog.sessionStart(
          authResult.session.user.userId || authResult.session.user.id || 'unknown',
          responseData.sessionId,
          ip
        );
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
    auditLog.error('api/orchestrator/session/start', error, ip);
    const response = handleApiError(error, 'api/orchestrator/session/start');
    return new Response(response.body, {
      status: response.status,
      headers: { ...Object.fromEntries(response.headers), ...getCorsHeaders(origin) },
    });
  }
}
