import { NextRequest } from "next/server";
import { requireAdmin } from "@/lib/auth-utils";
import { getCorsHeaders, corsOptionsResponse } from "@/lib/cors";
import { checkRateLimit, getClientId, rateLimitResponse } from "@/lib/rate-limiter";
import { handleApiError } from "@/lib/errors";
import { auditLog, getAuditIp } from "@/lib/audit";

export const runtime = "nodejs";

export async function OPTIONS(req: NextRequest) {
  return corsOptionsResponse(req);
}

export async function GET(req: NextRequest, { params }: { params: { id: string } }) {
  const origin = req.headers.get("origin");
  const ip = getAuditIp(req);

  try {
    // Require admin authentication
    const authResult = await requireAdmin();
    if (authResult.error) {
      return new Response(authResult.error.body, {
        status: 403,
        headers: { "Content-Type": "application/json", ...getCorsHeaders(origin) },
      });
    }

    // Rate limiting
    const clientId = getClientId(req, authResult.session.user.userId);
    const { allowed } = checkRateLimit(clientId, 'default');
    if (!allowed) {
      auditLog.rateLimited(clientId, 'admin/prompts/[id]/versions', ip);
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

    const target = `${base.replace(/\/$/, "")}/admin/prompts/${encodeURIComponent(params.id)}/versions`;
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
    auditLog.error('api/orchestrator/admin/prompts/[id]/versions', error, ip);
    const response = handleApiError(error, 'api/orchestrator/admin/prompts/[id]/versions');
    return new Response(response.body, {
      status: response.status,
      headers: { ...Object.fromEntries(response.headers), ...getCorsHeaders(origin) },
    });
  }
}
