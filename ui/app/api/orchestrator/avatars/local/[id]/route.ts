// =============================================================================
// Local Avatar API - Delete individual avatar
// =============================================================================

import { NextRequest, NextResponse } from "next/server";
import fs from "fs";
import path from "path";
import { requireAdmin } from "@/lib/auth-utils";
import { getCorsHeaders, corsOptionsResponse } from "@/lib/cors";
import { checkRateLimit, getClientId, rateLimitResponse } from "@/lib/rate-limiter";
import { handleApiError } from "@/lib/errors";
import { auditLog, getAuditIp } from "@/lib/audit";

export const dynamic = "force-dynamic";

// Data directory for avatars (relative to project root)
const DATA_DIR = process.env.AVATARS_DATA_DIR || path.join(process.cwd(), "data", "avatars");
const METADATA_FILE = path.join(DATA_DIR, "metadata.json");

interface AvatarMetadata {
  avatars: Record<string, {
    id: string;
    name: string;
    gender: string;
    style: string;
    downloaded_at: string;
    source: string;
    size_mb: number;
  }>;
}

function loadMetadata(): AvatarMetadata {
  if (fs.existsSync(METADATA_FILE)) {
    try {
      const data = fs.readFileSync(METADATA_FILE, "utf-8");
      return JSON.parse(data);
    } catch {
      return { avatars: {} };
    }
  }
  return { avatars: {} };
}

function saveMetadata(metadata: AvatarMetadata) {
  fs.writeFileSync(METADATA_FILE, JSON.stringify(metadata, null, 2));
}

export async function OPTIONS(req: NextRequest) {
  return corsOptionsResponse(req);
}

// GET - Get single avatar details
export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const origin = req.headers.get("origin");
  const ip = getAuditIp(req);

  try {
    // Rate limiting
    const clientId = getClientId(req);
    const { allowed } = checkRateLimit(clientId, 'default');
    if (!allowed) {
      auditLog.rateLimited(clientId, 'avatars/local/[id]', ip);
      const response = rateLimitResponse();
      return new Response(response.body, {
        status: response.status,
        headers: { ...Object.fromEntries(response.headers), ...getCorsHeaders(origin) },
      });
    }

    const { id } = await params;
    const avatarId = decodeURIComponent(id);
    const metadata = loadMetadata();

    if (!metadata.avatars[avatarId]) {
      return NextResponse.json(
        { error: "Avatar not found" },
        { status: 404, headers: getCorsHeaders(origin) }
      );
    }

    return NextResponse.json({
      ...metadata.avatars[avatarId],
      id: avatarId,
      path: path.join(DATA_DIR, avatarId),
    }, {
      headers: getCorsHeaders(origin),
    });
  } catch (error) {
    auditLog.error('api/orchestrator/avatars/local/[id]', error, ip);
    const response = handleApiError(error, 'api/orchestrator/avatars/local/[id]');
    return new Response(response.body, {
      status: response.status,
      headers: { ...Object.fromEntries(response.headers), ...getCorsHeaders(origin) },
    });
  }
}

// DELETE - Remove avatar from metadata and delete files (admin only)
export async function DELETE(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const origin = req.headers.get("origin");
  const ip = getAuditIp(req);

  try {
    // Require admin authentication for deletion
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
      auditLog.rateLimited(clientId, 'avatars/local/[id]', ip);
      const response = rateLimitResponse();
      return new Response(response.body, {
        status: response.status,
        headers: { ...Object.fromEntries(response.headers), ...getCorsHeaders(origin) },
      });
    }

    const { id } = await params;
    const avatarId = decodeURIComponent(id);
    const metadata = loadMetadata();

    if (!metadata.avatars[avatarId]) {
      return NextResponse.json(
        { error: "Avatar not found" },
        { status: 404, headers: getCorsHeaders(origin) }
      );
    }

    const avatarName = metadata.avatars[avatarId].name;

    // Remove avatar directory if it exists
    const avatarDir = path.join(DATA_DIR, avatarId);
    if (fs.existsSync(avatarDir)) {
      fs.rmSync(avatarDir, { recursive: true, force: true });
    }

    // Remove from metadata
    delete metadata.avatars[avatarId];
    saveMetadata(metadata);

    // Log admin action
    auditLog.adminAction(
      authResult.session.user.userId || authResult.session.user.id || 'unknown',
      `delete_avatar:${avatarId}`,
      ip
    );

    return NextResponse.json({
      success: true,
      message: `Avatar "${avatarName}" deleted successfully`,
      deleted_id: avatarId,
    }, {
      headers: getCorsHeaders(origin),
    });
  } catch (error) {
    auditLog.error('api/orchestrator/avatars/local/[id]', error, ip);
    const response = handleApiError(error, 'api/orchestrator/avatars/local/[id]');
    return new Response(response.body, {
      status: response.status,
      headers: { ...Object.fromEntries(response.headers), ...getCorsHeaders(origin) },
    });
  }
}
