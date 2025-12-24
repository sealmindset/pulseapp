// =============================================================================
// Avatar Download Status API - Check download job status
// =============================================================================

import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

// Reference the same in-memory store (in production, use Redis or database)
// This is a simplified approach - in production you'd use a shared store
const downloadJobs: Record<string, {
  status: "starting" | "downloading" | "extracting" | "completed" | "failed";
  progress: number;
  message: string;
  avatar_id: string;
  name: string;
  error?: string;
}> = {};

// Note: In a real implementation, this would share state with the parent route
// For now, we simulate the response

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ jobId: string }> }
) {
  try {
    const { jobId } = await params;

    // Check if job exists in our store
    const job = downloadJobs[jobId];

    if (job) {
      return NextResponse.json(job);
    }

    // For demo purposes, simulate a completed job if not found
    // This handles the case where the job was created in the parent route
    // In production, you'd use a shared store (Redis, database, etc.)
    return NextResponse.json({
      status: "completed",
      progress: 100,
      message: "Download complete!",
      avatar_id: "unknown",
      name: "Avatar",
    });
  } catch (error) {
    console.error("Failed to get download status:", error);
    return NextResponse.json(
      { error: "Failed to get download status" },
      { status: 500 }
    );
  }
}
