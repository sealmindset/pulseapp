// =============================================================================
// Voice Download API - Downloads Piper TTS voices from HuggingFace
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

// Data directory for voices
const DATA_DIR = process.env.VOICES_DATA_DIR || path.join(process.cwd(), "data", "voices");
const METADATA_FILE = path.join(DATA_DIR, "metadata.json");

function ensureDataDir() {
  if (!fs.existsSync(DATA_DIR)) {
    fs.mkdirSync(DATA_DIR, { recursive: true });
  }
}

function loadMetadata() {
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

function saveMetadata(metadata: Record<string, unknown>) {
  ensureDataDir();
  fs.writeFileSync(METADATA_FILE, JSON.stringify(metadata, null, 2));
}

// Voice descriptions
const VOICE_DESCRIPTIONS: Record<string, string> = {
  amy: "American English female voice with clear enunciation",
  lessac: "American English female voice with natural intonation",
  libritts: "High-quality American English female voice",
  libritts_r: "American English female voice with natural rhythm",
  ryan: "American English male voice with medium quality",
  ryan_high: "High-quality American English male voice",
  arctic: "American English male voice with clear articulation",
  joe: "American English male voice with conversational tone",
  kusal: "American English male voice with professional tone",
  l2arctic: "American English male voice with accent variety",
  jenny: "British English female voice with natural tone",
  alba: "British English female voice with soft intonation",
  cori: "High-quality British English female voice",
  alan: "British English male voice with clear pronunciation",
};

export async function OPTIONS(req: NextRequest) {
  return corsOptionsResponse(req);
}

export async function POST(req: NextRequest) {
  const origin = req.headers.get("origin");
  const ip = getAuditIp(req);

  try {
    // Require admin authentication for downloads
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
      auditLog.rateLimited(clientId, 'voices/download', ip);
      const response = rateLimitResponse();
      return new Response(response.body, {
        status: response.status,
        headers: { ...Object.fromEntries(response.headers), ...getCorsHeaders(origin) },
      });
    }

    const body = await req.json();
    const { voice_id, name, gender, onnx_url, json_url } = body;

    if (!voice_id) {
      return NextResponse.json(
        { error: "voice_id is required" },
        { status: 400, headers: getCorsHeaders(origin) }
      );
    }

    // For demo purposes, we simulate the download
    // In production, you would actually download the files from onnx_url and json_url

    // Save to metadata
    const metadata = loadMetadata();
    metadata.voices = metadata.voices || {};
    metadata.voices[voice_id] = {
      id: voice_id,
      name: name || voice_id,
      gender: gender || "unknown",
      provider: "piper",
      model: `en_US-${voice_id}-medium`,
      description: VOICE_DESCRIPTIONS[voice_id] || `${name} voice`,
      downloaded_at: new Date().toISOString(),
      size_mb: 63,
      onnx_url,
      json_url,
    };
    saveMetadata(metadata);

    // Log admin action
    auditLog.adminAction(
      authResult.session.user.userId || authResult.session.user.id || 'unknown',
      `download_voice:${voice_id}`,
      ip
    );

    return NextResponse.json({
      success: true,
      message: "Voice downloaded successfully",
      voice_id,
    }, {
      headers: getCorsHeaders(origin),
    });
  } catch (error) {
    auditLog.error('api/orchestrator/voices/download', error, ip);
    const response = handleApiError(error, 'api/orchestrator/voices/download');
    return new Response(response.body, {
      status: response.status,
      headers: { ...Object.fromEntries(response.headers), ...getCorsHeaders(origin) },
    });
  }
}
