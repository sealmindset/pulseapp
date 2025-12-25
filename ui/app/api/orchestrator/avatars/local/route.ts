// =============================================================================
// Local Avatars API - Manages downloaded avatars
// =============================================================================

import { NextRequest, NextResponse } from "next/server";
import fs from "fs";
import path from "path";
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

function ensureDataDir() {
  if (!fs.existsSync(DATA_DIR)) {
    fs.mkdirSync(DATA_DIR, { recursive: true });
  }
}

function loadMetadata(): AvatarMetadata {
  ensureDataDir();
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

export async function OPTIONS(req: NextRequest) {
  return corsOptionsResponse(req);
}

export async function GET(req: NextRequest) {
  const origin = req.headers.get("origin");
  const ip = getAuditIp(req);

  try {
    // Rate limiting
    const clientId = getClientId(req);
    const { allowed } = checkRateLimit(clientId, 'default');
    if (!allowed) {
      auditLog.rateLimited(clientId, 'avatars/local', ip);
      const response = rateLimitResponse();
      return new Response(response.body, {
        status: response.status,
        headers: { ...Object.fromEntries(response.headers), ...getCorsHeaders(origin) },
      });
    }

    const metadata = loadMetadata();

    const avatars = Object.entries(metadata.avatars).map(([id, data]) => ({
      ...data,
      id, // Override any id in data with the key
      path: path.join(DATA_DIR, id),
    }));

    return NextResponse.json({
      avatars,
      total: avatars.length,
      data_dir: DATA_DIR,
    }, {
      headers: getCorsHeaders(origin),
    });
  } catch (error) {
    auditLog.error('api/orchestrator/avatars/local', error, ip);
    const response = handleApiError(error, 'api/orchestrator/avatars/local');
    return new Response(response.body, {
      status: response.status,
      headers: { ...Object.fromEntries(response.headers), ...getCorsHeaders(origin) },
    });
  }
}
