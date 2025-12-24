// =============================================================================
// Avatar Download API - Downloads avatars from ModelScope
// =============================================================================

import { NextRequest, NextResponse } from "next/server";
import fs from "fs";
import path from "path";

export const dynamic = "force-dynamic";

// Data directory for avatars
const DATA_DIR = process.env.AVATARS_DATA_DIR || path.join(process.cwd(), "data", "avatars");
const METADATA_FILE = path.join(DATA_DIR, "metadata.json");

// In-memory job tracking (in production, use Redis or database)
const downloadJobs: Record<string, {
  status: "starting" | "downloading" | "extracting" | "completed" | "failed";
  progress: number;
  message: string;
  avatar_id: string;
  name: string;
  error?: string;
}> = {};

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
      return { avatars: {} };
    }
  }
  return { avatars: {} };
}

function saveMetadata(metadata: Record<string, unknown>) {
  ensureDataDir();
  fs.writeFileSync(METADATA_FILE, JSON.stringify(metadata, null, 2));
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { avatar_id, name, gender, style } = body;

    if (!avatar_id) {
      return NextResponse.json(
        { error: "avatar_id is required" },
        { status: 400 }
      );
    }

    // Generate job ID
    const jobId = `job_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

    // Initialize job
    downloadJobs[jobId] = {
      status: "starting",
      progress: 0,
      message: "Initializing download...",
      avatar_id,
      name: name || avatar_id,
    };

    // Start download in background (simulated for demo)
    simulateDownload(jobId, avatar_id, name, gender, style);

    return NextResponse.json({
      job_id: jobId,
      status: "starting",
      message: "Download started",
    });
  } catch (error) {
    console.error("Failed to start avatar download:", error);
    return NextResponse.json(
      { error: "Failed to start download" },
      { status: 500 }
    );
  }
}

// Simulate download progress (in production, this would actually download the file)
async function simulateDownload(
  jobId: string,
  avatarId: string,
  name: string,
  gender: string,
  style: string
) {
  try {
    // Simulate download progress
    for (let progress = 10; progress <= 90; progress += 10) {
      await new Promise((resolve) => setTimeout(resolve, 300));
      downloadJobs[jobId] = {
        ...downloadJobs[jobId],
        status: "downloading",
        progress,
        message: `Downloading... ${progress}%`,
      };
    }

    // Simulate extraction
    downloadJobs[jobId] = {
      ...downloadJobs[jobId],
      status: "extracting",
      progress: 95,
      message: "Extracting files...",
    };
    await new Promise((resolve) => setTimeout(resolve, 500));

    // Save to metadata
    const metadata = loadMetadata();
    metadata.avatars = metadata.avatars || {};
    metadata.avatars[avatarId] = {
      id: avatarId,
      name: name || avatarId,
      gender: gender || "unknown",
      style: style || "casual-sitting",
      downloaded_at: new Date().toISOString(),
      source: "modelscope",
      size_mb: 45,
    };
    saveMetadata(metadata);

    // Mark complete
    downloadJobs[jobId] = {
      ...downloadJobs[jobId],
      status: "completed",
      progress: 100,
      message: "Download complete!",
    };

    // Clean up job after 5 minutes
    setTimeout(() => {
      delete downloadJobs[jobId];
    }, 5 * 60 * 1000);
  } catch (error) {
    downloadJobs[jobId] = {
      ...downloadJobs[jobId],
      status: "failed",
      progress: 0,
      message: "Download failed",
      error: error instanceof Error ? error.message : "Unknown error",
    };
  }
}

export async function GET(request: NextRequest) {
  // This endpoint is for listing all jobs (optional)
  return NextResponse.json({
    jobs: Object.entries(downloadJobs).map(([id, job]) => ({
      id,
      ...job,
    })),
  });
}
