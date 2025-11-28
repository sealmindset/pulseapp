"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import PersonaSelector from "@/components/PersonaSelector";
import ScenarioFilters from "@/components/ScenarioFilters";
import { useState } from "react";
import { useSession } from "@/components/SessionContext";

export default function PreSessionPage() {
  const router = useRouter();
  const { persona, filters, setSessionId, setAvatarUrl } = useSession();
  const [ack, setAck] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Optional pilot user id used to tag analytics/readiness. In a real
  // deployment this would come from auth; here we allow a debug UUID via env.
  const readinessUserId =
    process.env.NEXT_PUBLIC_PULSE_USER_ID || process.env.NEXT_PUBLIC_PULSE_READINESS_USER_ID || null;

  const startSession = async () => {
    setError(null);
    if (!persona) {
      setError("Please select a persona.");
      return;
    }
    if (!ack) {
      setError("Please confirm you understand the session goal.");
      return;
    }
    setLoading(true);
    try {
      const payload: any = { persona, filters, prerequisitesAccepted: true };
      if (readinessUserId) {
        payload.userId = readinessUserId;
      }
      const res = await fetch("/api/orchestrator/session/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error(`Failed to start session (${res.status})`);
      const json = await res.json();
      const sid = json.sessionId || json.id || null;
      if (!sid) throw new Error("No sessionId returned");
      setSessionId(sid);
      if (json.avatarUrl || json.avatar) {
        setAvatarUrl(json.avatarUrl || json.avatar);
      }
      router.push("/session");
    } catch (e: any) {
      setError(e.message || "Unable to start session");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Pre-Session</h1>
      <p className="text-sm text-gray-600">Select a persona and a scenario to begin a behavioral certification session.</p>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 space-y-6">
          <PersonaSelector />
        </div>
        <div>
          <ScenarioFilters />
        </div>
      </div>

      <div className="space-y-3">
        <div className="rounded border border-gray-200 p-4">
          <div className="text-sm font-medium">Prerequisites</div>
          <p className="mt-1 text-sm text-gray-600">Goal: Successfully use the LERA framework to overcome a price (C2) objection and compel a “YES” to Close Today.</p>
          <label className="mt-2 inline-flex items-center gap-2 text-sm">
            <input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} />
            <span>I understand and accept the goal.</span>
          </label>
        </div>

        {error && <div className="rounded border border-red-200 bg-red-50 p-2 text-sm text-red-700">{error}</div>}

        <div className="flex items-center gap-3">
          <button
            onClick={startSession}
            disabled={loading}
            className="inline-flex items-center rounded-md bg-black px-4 py-2 text-white hover:bg-gray-800 disabled:opacity-60"
          >
            {loading ? "Starting..." : "Start Session"}
          </button>
          <Link href="/admin" className="text-sm text-gray-600 underline">Admin</Link>
        </div>
      </div>
    </div>
  );
}
