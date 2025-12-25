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
    // Rate limiting - use chat limit for audio chunks
    const clientId = getClientId(req);
    const { allowed } = checkRateLimit(clientId, 'chat');
    if (!allowed) {
      auditLog.rateLimited(clientId, 'audio/chunk', ip);
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
    const target = `${base.replace(/\/$/, "")}/audio/chunk`;

    const res = await fetch(target, {
      method: "POST",
      headers: {
        "X-Function-Key": process.env.FUNCTION_APP_SHARED_SECRET || "",
      },
      body: form,
    });

    const data = await res.arrayBuffer();
    const headers = new Headers();
    // Copy content-type and other relevant headers
    const contentType = res.headers.get("Content-Type");
    if (contentType) headers.set("Content-Type", contentType);

    // Add CORS headers
    Object.entries(getCorsHeaders(origin)).forEach(([k, v]) => headers.set(k, v));

    return new Response(data, {
      status: res.status,
      headers,
    });
  } catch (error) {
    auditLog.error('api/orchestrator/audio/chunk', error, ip);
    const response = handleApiError(error, 'api/orchestrator/audio/chunk');
    return new Response(response.body, {
      status: response.status,
      headers: { ...Object.fromEntries(response.headers), ...getCorsHeaders(origin) },
    });
  }
}
