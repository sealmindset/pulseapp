import { NextRequest } from "next/server";
import { getCorsHeaders, corsOptionsResponse } from "@/lib/cors";
import { validateChatRequest, validationError } from "@/lib/validation";
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
    const { allowed } = checkRateLimit(clientId, 'chat');
    if (!allowed) {
      auditLog.rateLimited(clientId, 'chat', ip);
      const response = rateLimitResponse();
      return new Response(response.body, {
        status: response.status,
        headers: { ...Object.fromEntries(response.headers), ...getCorsHeaders(origin) },
      });
    }

    // Validate request
    const json = await req.json();
    const validation = validateChatRequest(json);
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

    const target = `${base.replace(/\/$/, "")}/chat`;

    const res = await fetch(target, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Function-Key": process.env.FUNCTION_APP_SHARED_SECRET || "",
      },
      body: JSON.stringify(json),
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
    auditLog.error('api/orchestrator/chat', error, ip);
    const response = handleApiError(error, 'api/orchestrator/chat');
    return new Response(response.body, {
      status: response.status,
      headers: { ...Object.fromEntries(response.headers), ...getCorsHeaders(origin) },
    });
  }
}
