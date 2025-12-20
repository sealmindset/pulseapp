"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSession } from "@/components/SessionContext";
import { ReadinessCard } from "@/components/ReadinessCard";
import SentimentGauge from "@/components/SentimentGauge";

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
          {/* Sale Outcome Banner */}
          {feedback?.scorecard?.pulse_details?.sale_outcome && (
            <div className={`rounded-lg p-4 ${
              feedback.scorecard.pulse_details.sale_outcome === "won" 
                ? "bg-green-50 border-2 border-green-500" 
                : "bg-red-50 border-2 border-red-500"
            }`}>
              <div className="flex items-center gap-4">
                <span className="text-4xl">
                  {feedback.scorecard.pulse_details.sale_outcome === "won" ? "🎉" : "😔"}
                </span>
                <div>
                  <div className={`text-xl font-bold ${
                    feedback.scorecard.pulse_details.sale_outcome === "won" ? "text-green-700" : "text-red-700"
                  }`}>
                    {feedback.scorecard.pulse_details.sale_outcome === "won" ? "Sale Won!" : "Sale Lost"}
                  </div>
                  <div className="text-sm text-gray-600">
                    Reached PULSE stage: {feedback.scorecard.pulse_details.stage_name} • 
                    Trust: {feedback.scorecard.pulse_details.trust_score}/10 • 
                    Exchanges: {feedback.scorecard.pulse_details.total_exchanges}
                  </div>
                </div>
              </div>
            </div>
          )}
          
          {/* Overall Score with Gauge */}
          <div className="rounded border border-gray-200 p-4">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-lg font-medium">Overall Score</div>
                <div className="mt-2 text-4xl font-bold">
                  {loading ? "Loading..." : (typeof scorePct === "number" ? `${scorePct}%` : "—")}
                </div>
                <div className="mt-1 text-sm text-gray-600">Minimum passing threshold: 70%</div>
                {typeof scorePct === "number" && (
                  <div className={`mt-2 inline-block px-3 py-1 rounded-full text-sm font-medium ${
                    scorePct >= 70 ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"
                  }`}>
                    {scorePct >= 70 ? "✓ Passed" : "✗ Needs Improvement"}
                  </div>
                )}
              </div>
              {feedback?.scorecard?.pulse_details?.trust_score !== undefined && (
                <div className="flex flex-col items-center">
                  <SentimentGauge 
                    trustScore={feedback.scorecard.pulse_details.trust_score} 
                    size="sm"
                    showLabels={true}
                  />
                  <div className="mt-6 text-xs text-gray-500">Final Customer Sentiment</div>
                </div>
              )}
            </div>
            {error && <div className="mt-2 rounded border border-red-200 bg-red-50 p-2 text-sm text-red-700">{error}</div>}
          </div>
          
          {/* Rubric Compliance */}
          <div className="rounded border border-gray-200 p-4">
            <div className="text-lg font-medium">Rubric Compliance</div>
            <div className="mt-4 space-y-3">
              {Array.isArray(feedback?.rubric) && feedback.rubric.length > 0 ? (
                feedback.rubric.map((r: any, idx: number) => (
                  <div key={idx} className="flex items-start gap-3 p-3 bg-gray-50 rounded-lg">
                    <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
                      r.passed ? "bg-green-100 text-green-600" : "bg-red-100 text-red-600"
                    }`}>
                      {r.passed ? "✓" : "✗"}
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-medium">{r.name || r.label || `Criterion ${idx + 1}`}</span>
                        {typeof r.score !== "undefined" && (
                          <span className="text-sm px-2 py-0.5 bg-gray-200 rounded">{r.score}/3</span>
                        )}
                      </div>
                      {r.notes && <div className="mt-1 text-sm text-gray-600">{r.notes}</div>}
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-sm text-gray-600">Rubric details will appear after the session concludes.</div>
              )}
            </div>
          </div>
          
          {/* Missteps Section */}
          {feedback?.scorecard?.pulse_details?.missteps?.length > 0 && (
            <div className="rounded border border-red-200 bg-red-50 p-4">
              <div className="text-lg font-medium text-red-700">Missteps Detected</div>
              <ul className="mt-2 space-y-1">
                {feedback.scorecard.pulse_details.missteps.map((misstep: string, idx: number) => (
                  <li key={idx} className="flex items-center gap-2 text-sm text-red-600">
                    <span>⚠️</span>
                    <span className="capitalize">{misstep}</span>
                  </li>
                ))}
              </ul>
              <div className="mt-3 text-sm text-gray-600">
                Avoid these behaviors in future sessions to improve your score.
              </div>
            </div>
          )}
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
