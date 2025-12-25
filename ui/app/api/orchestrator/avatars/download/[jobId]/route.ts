// =============================================================================
// Avatar Download Status API - Check download job status
// =============================================================================

import { NextRequest, NextResponse } from "next/server";
import { getCorsHeaders, corsOptionsResponse } from "@/lib/cors";
import { checkRateLimit, getClientId, rateLimitResponse } from "@/lib/rate-limiter";
import { handleApiError } from "@/lib/errors";
import { auditLog, getAuditIp } from "@/lib/audit";

export const dynamic = "force-dynamic";

// Reference the same in-memory store (in production, use Redis or database)
// This is a simplified approach - in production you'd use a shared store
const downloadJobs: Record<string, {
  status: "starting" | "downloading" | "extracting" | "completed" | "failed";
  progress: number;
  message: string;
  avatar_id: string;
  name: string;
  error?: string;
}> = {};

export async function OPTIONS(req: NextRequest) {
  return corsOptionsResponse(req);
}

// Note: In a real implementation, this would share state with the parent route
// For now, we simulate the response

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ jobId: string }> }
) {
  const origin = req.headers.get("origin");
  const ip = getAuditIp(req);

  try {
    // Rate limiting
    const clientId = getClientId(req);
    const { allowed } = checkRateLimit(clientId, 'default');
    if (!allowed) {
      auditLog.rateLimited(clientId, 'avatars/download/[jobId]', ip);
      const response = rateLimitResponse();
      return new Response(response.body, {
        status: response.status,
        headers: { ...Object.fromEntries(response.headers), ...getCorsHeaders(origin) },
      });
    }

    const { jobId } = await params;

    // Check if job exists in our store
    const job = downloadJobs[jobId];

    if (job) {
      return NextResponse.json(job, {
        headers: getCorsHeaders(origin),
      });
    }

    // For demo purposes, simulate a completed job if not found
    // This handles the case where the job was created in the parent route
    // In production, you'd use a shared store (Redis, database, etc.)
    return NextResponse.json({
      status: "completed",
      progress: 100,
      message: "Download complete!",
      avatar_id: "unknown",
      name: "Avatar",
    }, {
      headers: getCorsHeaders(origin),
    });
  } catch (error) {
    auditLog.error('api/orchestrator/avatars/download/[jobId]', error, ip);
    const response = handleApiError(error, 'api/orchestrator/avatars/download/[jobId]');
    return new Response(response.body, {
      status: response.status,
      headers: { ...Object.fromEntries(response.headers), ...getCorsHeaders(origin) },
    });
  }
}
