// =============================================================================
// Local Avatars API - Manages downloaded avatars
// =============================================================================

import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";

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

function saveMetadata(metadata: AvatarMetadata) {
  ensureDataDir();
  fs.writeFileSync(METADATA_FILE, JSON.stringify(metadata, null, 2));
}

export async function GET() {
  try {
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
    });
  } catch (error) {
    console.error("Failed to fetch local avatars:", error);
    return NextResponse.json(
      { error: "Failed to fetch local avatars" },
      { status: 500 }
    );
  }
}
