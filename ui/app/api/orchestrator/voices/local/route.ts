// =============================================================================
// Local Voices API - Manages downloaded Piper TTS voices
// =============================================================================

import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";

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

export async function GET() {
  try {
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
    });
  } catch (error) {
    console.error("Failed to fetch local voices:", error);
    return NextResponse.json(
      { error: "Failed to fetch local voices" },
      { status: 500 }
    );
  }
}
