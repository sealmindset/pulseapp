// =============================================================================
// Avatar Catalog API - Returns available avatars from ModelScope catalog
// =============================================================================

import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

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

export async function GET() {
  try {
    // Build catalog with thumbnail URLs - all thumbnails are local
    const avatars = AVATAR_CATALOG.map((avatar) => ({
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
    });
  } catch (error) {
    console.error("Failed to fetch avatar catalog:", error);
    return NextResponse.json(
      { error: "Failed to fetch avatar catalog" },
      { status: 500 }
    );
  }
}
