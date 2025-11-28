"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSession } from "@/components/SessionContext";
import { ReadinessCard } from "@/components/ReadinessCard";

export default function FeedbackPage() {
  const { sessionId } = useSession();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<any>(null);

  // Optional debug user id for showing readiness; if not set, readiness is hidden.
  const readinessUserId = process.env.NEXT_PUBLIC_PULSE_READINESS_USER_ID || null;

  useEffect(() => {
    let cancelled = false;
    async function run() {
      if (!sessionId) return;
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(`/api/orchestrator/feedback/${encodeURIComponent(sessionId)}`);
        const ct = res.headers.get("content-type") || "";
        const data = ct.includes("application/json") ? await res.json() : await res.text();
        if (!cancelled) setFeedback(data);
      } catch (e: any) {
        if (!cancelled) setError(e.message || "Failed to load feedback");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    run();
    return () => { cancelled = true; };
  }, [sessionId]);

  const scorePct = useMemo(() => {
    const raw = feedback?.overallScore ?? feedback?.score ?? feedback?.mastery;
    const num = typeof raw === "number" ? raw : parseFloat(raw);
    if (!isFinite(num)) return null;
    return num > 1 ? Math.round(num) : Math.round(num * 100);
  }, [feedback]);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Feedback & Scoring</h1>
      <p className="text-sm text-gray-600">Review your Behavioral Mastery score and rubric breakdown.</p>
      {!sessionId && (
        <div className="rounded border border-yellow-200 bg-yellow-50 p-2 text-sm text-yellow-800">
          No active session. Please start a new one from the Pre-Session page. <Link href="/" className="underline">Start</Link>
        </div>
      )}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 space-y-4">
          <div className="rounded border border-gray-200 p-4">
            <div className="text-lg font-medium">Overall Score</div>
            <div className="mt-2 text-4xl font-bold">
              {loading ? "Loading..." : (typeof scorePct === "number" ? `${scorePct}%` : "—")}
            </div>
            <div className="mt-1 text-sm text-gray-600">Minimum passing threshold: 85%</div>
            {error && <div className="mt-2 rounded border border-red-200 bg-red-50 p-2 text-sm text-red-700">{error}</div>}
          </div>
          <div className="rounded border border-gray-200 p-4">
            <div className="text-lg font-medium">Rubric Compliance</div>
            <div className="mt-2">
              {Array.isArray(feedback?.rubric) ? (
                <ul className="list-disc pl-6 text-sm text-gray-700">
                  {feedback.rubric.map((r: any, idx: number) => (
                    <li key={idx}>
                      {r.name || r.label || `Criterion ${idx + 1}`}
                      {typeof r.score !== "undefined" && <span className="ml-2 text-gray-500">({r.score})</span>}
                      {typeof r.passed !== "undefined" && (
                        <span className={`ml-2 ${r.passed ? "text-green-600" : "text-red-600"}`}>{r.passed ? "Passed" : "Needs work"}</span>
                      )}
                      {r.notes && <span className="ml-2 text-gray-500">— {r.notes}</span>}
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="text-sm text-gray-600">Rubric details will appear after scoring.</div>
              )}
            </div>
          </div>
        </div>
        <div className="space-y-4">
          <div className="rounded border border-gray-200 p-4">
            <div className="text-lg font-medium">Artifacts</div>
            <div className="mt-2 space-y-3 text-sm text-gray-700">
              {(() => {
                const a: any = feedback?.artifacts || feedback?.outputs || {};
                const audioDataUrl = a?.audioBase64 ? `data:audio/mpeg;base64,${a.audioBase64}` : null;
                const transcript: string[] = Array.isArray(a?.transcript)
                  ? a.transcript
                  : (typeof a?.transcript === "string" ? [a.transcript] : []);
                return (
                  <>
                    {(a?.audioUrl || audioDataUrl) ? (
                      <div>
                        <div className="mb-1 font-medium">Audio</div>
                        <audio controls src={a?.audioUrl || audioDataUrl || undefined} />
                      </div>
                    ) : (
                      <div>Audio — (not available)</div>
                    )}
                    <div>
                      <div className="mb-1 font-medium">Transcript</div>
                      {transcript.length ? (
                        <div className="space-y-1">
                          {transcript.map((line, idx) => (
                            <div key={idx}>{line}</div>
                          ))}
                        </div>
                      ) : (
                        <div>Transcript — (not available)</div>
                      )}
                    </div>
                  </>
                );
              })()}
            </div>
          </div>
          {readinessUserId && <ReadinessCard userId={readinessUserId} />}
        </div>
      </div>
    </div>
  );
}
