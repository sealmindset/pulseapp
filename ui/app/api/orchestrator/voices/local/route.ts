// =============================================================================
// Local Voices API - Manages downloaded Piper TTS voices
// =============================================================================

import { NextRequest, NextResponse } from "next/server";
import fs from "fs";
import path from "path";
import { getCorsHeaders, corsOptionsResponse } from "@/lib/cors";
import { checkRateLimit, getClientId, rateLimitResponse } from "@/lib/rate-limiter";
import { handleApiError } from "@/lib/errors";
import { auditLog, getAuditIp } from "@/lib/audit";

export const dynamic = "force-dynamic";

// Data directory for voices (relative to project root)
const DATA_DIR = process.env.VOICES_DATA_DIR || path.join(process.cwd(), "data", "voices");
const METADATA_FILE = path.join(DATA_DIR, "metadata.json");

interface VoiceMetadata {
  voices: Record<string, {
    id: string;
    name: string;
    gender: string;
    provider: string;
    model: string;
    description: string;
    downloaded_at: string;
    size_mb: number;
  }>;
}

function ensureDataDir() {
  if (!fs.existsSync(DATA_DIR)) {
    fs.mkdirSync(DATA_DIR, { recursive: true });
  }
}

function loadMetadata(): VoiceMetadata {
  ensureDataDir();
  if (fs.existsSync(METADATA_FILE)) {
    try {
      const data = fs.readFileSync(METADATA_FILE, "utf-8");
      return JSON.parse(data);
    } catch {
      return { voices: {} };
    }
  }
  return { voices: {} };
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
      auditLog.rateLimited(clientId, 'voices/local', ip);
      const response = rateLimitResponse();
      return new Response(response.body, {
        status: response.status,
        headers: { ...Object.fromEntries(response.headers), ...getCorsHeaders(origin) },
      });
    }

    const metadata = loadMetadata();

    const voices = Object.entries(metadata.voices).map(([id, data]) => ({
      ...data,
      id, // Override any id in data with the key
      path: path.join(DATA_DIR, id),
    }));

    return NextResponse.json({
      voices,
      total: voices.length,
      data_dir: DATA_DIR,
    }, {
      headers: getCorsHeaders(origin),
    });
  } catch (error) {
    auditLog.error('api/orchestrator/voices/local', error, ip);
    const response = handleApiError(error, 'api/orchestrator/voices/local');
    return new Response(response.body, {
      status: response.status,
      headers: { ...Object.fromEntries(response.headers), ...getCorsHeaders(origin) },
    });
  }
}
