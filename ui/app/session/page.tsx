"use client";

import { useEffect, useRef, useState } from "react";
import PulseProgressBar from "@/components/SbnProgressBar";
import { useSession } from "@/components/SessionContext";
import { useRouter } from "next/navigation";

export default function SessionPage() {
  const router = useRouter();
  const { sessionId, avatarUrl } = useSession();
  const [recording, setRecording] = useState(false);
  const [transcript, setTranscript] = useState<string[]>([]);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);

  useEffect(() => {
    return () => {
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
        mediaRecorderRef.current.stop();
      }
    };
  }, []);

  const playAudioBlob = async (blob: Blob) => {
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    try {
      await audio.play();
    } catch {}
  };

  const uploadChunk = async (blob: Blob) => {
    const form = new FormData();
    if (sessionId) form.append("sessionId", sessionId);
    form.append("chunk", blob, "audio.webm");

    try {
      const res = await fetch("/api/orchestrator/audio/chunk", { method: "POST", body: form });
      const ct = res.headers.get("content-type") || "";
      if (ct.includes("application/json")) {
        const data = await res.json();
        if (data.partialTranscript) {
          setTranscript((t) => [...t, String(data.partialTranscript)]);
        }
        if (data.ttsUrl) {
          const a = new Audio(data.ttsUrl);
          try { await a.play(); } catch {}
        }
        if (data.audioBase64) {
          const b = await fetch(`data:audio/mpeg;base64,${data.audioBase64}`).then(r => r.blob());
          await playAudioBlob(b);
        }
      } else if (ct.startsWith("audio/")) {
        const audioBlob = await res.blob();
        await playAudioBlob(audioBlob);
      } else {
        // Fallback: treat as text
        const txt = await res.text();
        if (txt) setTranscript((t) => [...t, txt]);
      }
    } catch (e) {
      // swallow network errors for now; can add toast
    }
  };

  const startRecording = async () => {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const rec = new MediaRecorder(stream, { mimeType: "audio/webm" });
    mediaRecorderRef.current = rec;

    rec.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) {
        // upload each chunk as it arrives to simulate realtime
        uploadChunk(e.data);
      }
    };

    rec.start(1000); // collect data every second
    setRecording(true);
  };

  const stopRecording = () => {
    mediaRecorderRef.current?.stop();
    setRecording(false);
  };

  const completeSession = async () => {
    if (!sessionId) return;
    try {
      const res = await fetch("/api/orchestrator/session/complete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sessionId }),
      });
      if (!res.ok) throw new Error("Failed to complete session");
    } finally {
      router.push("/feedback");
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Session</h1>

      <PulseProgressBar currentStep={1} />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 space-y-4">
          <div className="aspect-video w-full overflow-hidden rounded border border-gray-200 bg-gray-50">
            {avatarUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={avatarUrl} alt="Persona Avatar" className="h-full w-full object-cover" />
            ) : (
              <div className="flex h-full items-center justify-center text-sm text-gray-500">Avatar will appear here</div>
            )}
          </div>
          <div className="flex gap-3">
            {!recording ? (
              <button onClick={startRecording} className="rounded bg-black px-4 py-2 text-white hover:bg-gray-800">Start Mic</button>
            ) : (
              <button onClick={stopRecording} className="rounded bg-red-600 px-4 py-2 text-white hover:bg-red-500">Stop Mic</button>
            )}
            <button onClick={completeSession} className="rounded border border-gray-300 px-4 py-2 text-gray-800 hover:bg-gray-50">Complete Session</button>
          </div>
        </div>
        <div>
          <div className="rounded border border-gray-200 p-4">
            <div className="font-medium">Transcript</div>
            <div className="mt-2 space-y-2 text-sm text-gray-700">
              {transcript.map((line, idx) => (
                <div key={idx}>{line}</div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
