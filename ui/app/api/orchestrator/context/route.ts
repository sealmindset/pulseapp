import { NextRequest } from "next/server";
import { getCorsHeaders, corsOptionsResponse } from "@/lib/cors";
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
    const { allowed } = checkRateLimit(clientId, 'default');
    if (!allowed) {
      auditLog.rateLimited(clientId, 'context', ip);
      const response = rateLimitResponse();
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

    const form = await req.formData();
    const target = `${base.replace(/\/$/, "")}/context`;

    const res = await fetch(target, {
      method: "POST",
      headers: {
        "X-Function-Key": process.env.FUNCTION_APP_SHARED_SECRET || "",
      },
      body: form,
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
    auditLog.error('api/orchestrator/context', error, ip);
    const response = handleApiError(error, 'api/orchestrator/context');
    return new Response(response.body, {
      status: response.status,
      headers: { ...Object.fromEntries(response.headers), ...getCorsHeaders(origin) },
    });
  }
}
