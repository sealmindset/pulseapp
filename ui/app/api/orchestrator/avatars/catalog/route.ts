// =============================================================================
// Avatar Catalog API - Returns available avatars from ModelScope catalog
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

// Data directory for catalog settings
const DATA_DIR = process.env.AVATARS_DATA_DIR || path.join(process.cwd(), "data", "avatars");
const HIDDEN_AVATARS_FILE = path.join(DATA_DIR, "hidden-avatars.json");

interface HiddenAvatarsData {
  hidden: string[]; // Array of avatar IDs that have been hidden/removed from catalog
}

function ensureDataDir() {
  if (!fs.existsSync(DATA_DIR)) {
    fs.mkdirSync(DATA_DIR, { recursive: true });
  }
}

function loadHiddenAvatars(): HiddenAvatarsData {
  ensureDataDir();
  if (fs.existsSync(HIDDEN_AVATARS_FILE)) {
    try {
      const data = fs.readFileSync(HIDDEN_AVATARS_FILE, "utf-8");
      return JSON.parse(data);
    } catch {
      return { hidden: [] };
    }
  }
  return { hidden: [] };
}

function saveHiddenAvatars(data: HiddenAvatarsData) {
  ensureDataDir();
  fs.writeFileSync(HIDDEN_AVATARS_FILE, JSON.stringify(data, null, 2));
}

// Avatar catalog from ModelScope LiteAvatar Gallery
// https://modelscope.cn/models/HumanAIGC-Engineering/LiteAvatarGallery
// All thumbnails are downloaded locally in /public/avatars/
// Name-to-ID mappings synced from dockerpulse/api/avatar_manager.py AVATAR_CATALOG
const AVATAR_CATALOG = [
  // Female avatars (13) - from dockerpulse catalog + 1 additional
  { id: "P1-aEYbtyyVpaMF2dSSpMxCw", name: "Mia", gender: "female", style: "casual", batch: "20250408", size_mb: 45 }, // Additional avatar
  { id: "P1lXrpJL507-PZ4hMPutyF7A", name: "Aria", gender: "female", style: "casual", batch: "20250408", size_mb: 45 },
  { id: "P1VXATUY6mm7CJLZ6CARKU0Q", name: "Bella", gender: "female", style: "casual", batch: "20250408", size_mb: 45 },
  { id: "P1bywtN2wUs4zbOIctjYZpjw", name: "Clara", gender: "female", style: "professional", batch: "20250408", size_mb: 45 },
  { id: "P11EW-z1MQ7qDBxbdFkzPPng", name: "Diana", gender: "female", style: "casual", batch: "20250408", size_mb: 45 },
  { id: "P1tkdZGlULMxNRWB3nsrucSA", name: "Elena", gender: "female", style: "professional", batch: "20250408", size_mb: 45 },
  { id: "P1lQSCriJLhJCbJfoOufApGw", name: "Fiona", gender: "female", style: "casual", batch: "20250408", size_mb: 45 },
  { id: "P1DB_Y1K6USuq-Nlun6Bh94A", name: "Grace", gender: "female", style: "professional", batch: "20250408", size_mb: 45 },
  { id: "P1yerb8kIA7eBpaIydU2lwzA", name: "Hannah", gender: "female", style: "casual", batch: "20250408", size_mb: 45 },
  { id: "P1tDSmoZ2olUyEqDslDH_cnQ", name: "Iris", gender: "female", style: "professional", batch: "20250408", size_mb: 45 },
  { id: "P1mmEbsQ19oc-16L27yA0_ew", name: "Julia", gender: "female", style: "casual", batch: "20250408", size_mb: 45 },
  { id: "P1CgOolwJwkGaZLu3BDN6S_w", name: "Kate", gender: "female", style: "professional", batch: "20250408", size_mb: 45 },
  { id: "P1sd8kz0dw2_2wl7m97UVjSQ", name: "Luna", gender: "female", style: "casual", batch: "20250408", size_mb: 45 },
  // Male avatars (10) - from dockerpulse catalog
  { id: "P1S9eH2OIYF1HgVyM2-2OK4g", name: "Alex", gender: "male", style: "casual", batch: "20250408", size_mb: 45 },
  { id: "P1u82oEWvPea73MT96wWTK-g", name: "Brian", gender: "male", style: "professional", batch: "20250408", size_mb: 45 },
  { id: "P1JBluxvgTS5ynI_lKtw64LQ", name: "Chris", gender: "male", style: "casual", batch: "20250408", size_mb: 45 },
  { id: "P1j2fUp4WJH7v5NlZrEDK_nw", name: "David", gender: "male", style: "professional", batch: "20250408", size_mb: 45 },
  { id: "P11eXAt1qfgYGyiJnbKy5Zow", name: "Eric", gender: "male", style: "casual", batch: "20250408", size_mb: 45 },
  { id: "P16F_-yXUzcnhqYhWTsW310w", name: "Frank", gender: "male", style: "professional", batch: "20250408", size_mb: 45 },
  { id: "P1HypyfUJfi6ZJawOSSN7GqA", name: "George", gender: "male", style: "casual", batch: "20250408", size_mb: 45 },
  { id: "P12rUIdDyWToybp-B0DCefSQ", name: "Henry", gender: "male", style: "professional", batch: "20250408", size_mb: 45 },
  { id: "P1PQc-xB-UC_y-Cm1D9POa8w", name: "Ivan", gender: "male", style: "casual", batch: "20250408", size_mb: 45 },
  { id: "P1dZg4pbDQ0OvEBvexPszwtw", name: "Jake", gender: "male", style: "professional", batch: "20250408", size_mb: 45 },
];

const BASE_URL = "https://modelscope.cn/models/HumanAIGC-Engineering/LiteAvatarGallery/resolve/master";

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
      auditLog.rateLimited(clientId, 'avatars/catalog', ip);
      const response = rateLimitResponse();
      return new Response(response.body, {
        status: response.status,
        headers: { ...Object.fromEntries(response.headers), ...getCorsHeaders(origin) },
      });
    }

    // Load hidden avatars list
    const hiddenData = loadHiddenAvatars();

    // Build catalog with thumbnail URLs - all thumbnails are local
    // Filter out hidden avatars
    const avatars = AVATAR_CATALOG
      .filter((avatar) => !hiddenData.hidden.includes(avatar.id))
      .map((avatar) => ({
        ...avatar,
        thumbnail_url: `/avatars/${avatar.id}.png`,
        download_url: `${BASE_URL}/${avatar.id}.zip`,
      }));

    // Group by batch
    const batches = [
      {
        id: "20250408",
        name: "April 2025 Collection",
        count: avatars.length,
        description: "High-quality LiteAvatar models from ModelScope",
        release_date: "2025-04-08",
      },
    ];

    return NextResponse.json({
      batches,
      avatars,
      total: avatars.length,
      hidden_count: hiddenData.hidden.length,
    }, {
      headers: getCorsHeaders(origin),
    });
  } catch (error) {
    auditLog.error('api/orchestrator/avatars/catalog', error, ip);
    const response = handleApiError(error, 'api/orchestrator/avatars/catalog');
    return new Response(response.body, {
      status: response.status,
      headers: { ...Object.fromEntries(response.headers), ...getCorsHeaders(origin) },
    });
  }
}

// DELETE - Hide/remove an avatar from the catalog (admin only)
export async function DELETE(req: NextRequest) {
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
      auditLog.rateLimited(clientId, 'avatars/catalog', ip);
      const response = rateLimitResponse();
      return new Response(response.body, {
        status: response.status,
        headers: { ...Object.fromEntries(response.headers), ...getCorsHeaders(origin) },
      });
    }

    const { searchParams } = new URL(req.url);
    const avatarId = searchParams.get("id");

    if (!avatarId) {
      return NextResponse.json(
        { error: "Avatar ID is required" },
        { status: 400, headers: getCorsHeaders(origin) }
      );
    }

    // Check if avatar exists in catalog
    const avatar = AVATAR_CATALOG.find((a) => a.id === avatarId);
    if (!avatar) {
      return NextResponse.json(
        { error: "Avatar not found in catalog" },
        { status: 404, headers: getCorsHeaders(origin) }
      );
    }

    // Load current hidden list and add this avatar
    const hiddenData = loadHiddenAvatars();

    if (hiddenData.hidden.includes(avatarId)) {
      return NextResponse.json(
        { error: "Avatar is already hidden" },
        { status: 400, headers: getCorsHeaders(origin) }
      );
    }

    hiddenData.hidden.push(avatarId);
    saveHiddenAvatars(hiddenData);

    // Log admin action
    auditLog.adminAction(
      authResult.session.user.userId || authResult.session.user.id || 'unknown',
      `hide_avatar:${avatarId}`,
      ip
    );

    return NextResponse.json({
      success: true,
      message: `Avatar "${avatar.name}" removed from catalog`,
      hidden_id: avatarId,
      hidden_count: hiddenData.hidden.length,
    }, {
      headers: getCorsHeaders(origin),
    });
  } catch (error) {
    auditLog.error('api/orchestrator/avatars/catalog', error, ip);
    const response = handleApiError(error, 'api/orchestrator/avatars/catalog');
    return new Response(response.body, {
      status: response.status,
      headers: { ...Object.fromEntries(response.headers), ...getCorsHeaders(origin) },
    });
  }
}
