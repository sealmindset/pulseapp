// =============================================================================
// Local Avatar API - Delete individual avatar
// =============================================================================

import { NextRequest, NextResponse } from "next/server";
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

// GET - Get single avatar details
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const avatarId = decodeURIComponent(id);
    const metadata = loadMetadata();

    if (!metadata.avatars[avatarId]) {
      return NextResponse.json(
        { error: "Avatar not found" },
        { status: 404 }
      );
    }

    return NextResponse.json({
      ...metadata.avatars[avatarId],
      id: avatarId,
      path: path.join(DATA_DIR, avatarId),
    });
  } catch (error) {
    console.error("Failed to fetch avatar:", error);
    return NextResponse.json(
      { error: "Failed to fetch avatar" },
      { status: 500 }
    );
  }
}

// DELETE - Remove avatar from metadata and delete files
export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const avatarId = decodeURIComponent(id);
    const metadata = loadMetadata();

    if (!metadata.avatars[avatarId]) {
      return NextResponse.json(
        { error: "Avatar not found" },
        { status: 404 }
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

    return NextResponse.json({
      success: true,
      message: `Avatar "${avatarName}" deleted successfully`,
      deleted_id: avatarId,
    });
  } catch (error) {
    console.error("Failed to delete avatar:", error);
    return NextResponse.json(
      { error: "Failed to delete avatar" },
      { status: 500 }
    );
  }
}
