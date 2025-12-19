"use client";

import { useEffect, useRef, useState } from "react";
import PulseProgressBar from "@/components/SbnProgressBar";
import { useSession, AvatarState } from "@/components/SessionContext";
import { useRouter } from "next/navigation";

type TranscriptEntry = {
  role: "user" | "assistant";
  content: string;
  timestamp: string;
};

export default function SessionPage() {
  const router = useRouter();
  const { 
    sessionId, 
    avatarUrl, 
    avatarVideoUrl, 
    avatarState, 
    personaInfo,
    setAvatarState,
    setAvatarVideoUrl,
  } = useSession();
  
  const [recording, setRecording] = useState(false);
  const [transcript, setTranscript] = useState<TranscriptEntry[]>([]);
  const [currentVideoSrc, setCurrentVideoSrc] = useState<string | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  // Initialize with intro video if available
  useEffect(() => {
    if (avatarVideoUrl && !currentVideoSrc) {
      setCurrentVideoSrc(avatarVideoUrl);
    }
  }, [avatarVideoUrl, currentVideoSrc]);

  useEffect(() => {
    return () => {
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
        mediaRecorderRef.current.stop();
      }
    };
  }, []);

  const playAudioBlob = async (blob: Blob) => {
    const url = URL.createObjectURL(blob);
    if (audioRef.current) {
      audioRef.current.src = url;
      try {
        await audioRef.current.play();
      } catch {}
    } else {
      const audio = new Audio(url);
      try {
        await audio.play();
      } catch {}
    }
  };

  const handleVideoEnded = () => {
    setAvatarState("idle");
  };

  const uploadChunk = async (blob: Blob) => {
    const form = new FormData();
    if (sessionId) form.append("sessionId", sessionId);
    form.append("chunk", blob, "audio.webm");

    setAvatarState("listening");

    try {
      const res = await fetch("/api/orchestrator/audio/chunk", { method: "POST", body: form });
      const ct = res.headers.get("content-type") || "";
      
      if (ct.includes("application/json")) {
        const data = await res.json();
        
        // Add user transcript
        if (data.partialTranscript) {
          setTranscript((t) => [...t, {
            role: "user",
            content: String(data.partialTranscript),
            timestamp: new Date().toISOString(),
          }]);
        }
        
        // Add AI response to transcript
        if (data.aiResponse) {
          setTranscript((t) => [...t, {
            role: "assistant",
            content: String(data.aiResponse),
            timestamp: new Date().toISOString(),
          }]);
        }
        
        // Handle avatar video (Sora-2)
        if (data.avatarVideo) {
          setAvatarState("speaking");
          if (data.avatarVideo.url) {
            setCurrentVideoSrc(data.avatarVideo.url);
          } else if (data.avatarVideo.base64) {
            const videoBlob = await fetch(`data:video/mp4;base64,${data.avatarVideo.base64}`).then(r => r.blob());
            setCurrentVideoSrc(URL.createObjectURL(videoBlob));
          }
        }
        
        // Handle audio response (TTS)
        if (data.audioBase64) {
          setAvatarState("speaking");
          const audioBlob = await fetch(`data:audio/mpeg;base64,${data.audioBase64}`).then(r => r.blob());
          await playAudioBlob(audioBlob);
        } else if (data.ttsUrl) {
          setAvatarState("speaking");
          const a = new Audio(data.ttsUrl);
          a.onended = () => setAvatarState("idle");
          try { await a.play(); } catch {}
        }
        
        // Update avatar state from response
        if (data.avatarState) {
          setAvatarState(data.avatarState as AvatarState);
        }
        
      } else if (ct.startsWith("audio/")) {
        setAvatarState("speaking");
        const audioBlob = await res.blob();
        await playAudioBlob(audioBlob);
      } else {
        const txt = await res.text();
        if (txt) {
          setTranscript((t) => [...t, {
            role: "assistant",
            content: txt,
            timestamp: new Date().toISOString(),
          }]);
        }
      }
    } catch (e) {
      console.error("Audio chunk upload failed:", e);
      setAvatarState("idle");
    }
  };

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const rec = new MediaRecorder(stream, { mimeType: "audio/webm" });
      mediaRecorderRef.current = rec;

      rec.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) {
          uploadChunk(e.data);
        }
      };

      rec.start(1000);
      setRecording(true);
      setAvatarState("listening");
    } catch (err) {
      console.error("Failed to start recording:", err);
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current) {
      mediaRecorderRef.current.stop();
      mediaRecorderRef.current.stream.getTracks().forEach(track => track.stop());
    }
    setRecording(false);
    setAvatarState("idle");
  };

  const completeSession = async () => {
    if (!sessionId) return;
    stopRecording();
    try {
      const res = await fetch("/api/orchestrator/session/complete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          sessionId, 
          transcript: transcript.map(t => `${t.role}: ${t.content}`).join("\n"),
        }),
      });
      if (!res.ok) throw new Error("Failed to complete session");
    } finally {
      router.push("/feedback");
    }
  };

  // Avatar state indicator styles
  const getAvatarStateIndicator = () => {
    switch (avatarState) {
      case "speaking":
        return <span className="absolute top-2 right-2 flex h-3 w-3"><span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span><span className="relative inline-flex rounded-full h-3 w-3 bg-green-500"></span></span>;
      case "listening":
        return <span className="absolute top-2 right-2 flex h-3 w-3"><span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span><span className="relative inline-flex rounded-full h-3 w-3 bg-blue-500"></span></span>;
      case "thinking":
        return <span className="absolute top-2 right-2 flex h-3 w-3"><span className="animate-pulse absolute inline-flex h-full w-full rounded-full bg-yellow-400 opacity-75"></span><span className="relative inline-flex rounded-full h-3 w-3 bg-yellow-500"></span></span>;
      default:
        return null;
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Training Session</h1>
        {personaInfo && (
          <span className="text-sm text-gray-600">
            Persona: <span className="font-medium">{personaInfo.displayName}</span>
          </span>
        )}
      </div>

      <PulseProgressBar currentStep={1} />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 space-y-4">
          {/* Avatar Video/Image Display */}
          <div className="relative aspect-video w-full overflow-hidden rounded-lg border border-gray-200 bg-gray-900">
            {getAvatarStateIndicator()}
            
            {currentVideoSrc ? (
              <video
                ref={videoRef}
                src={currentVideoSrc}
                autoPlay
                playsInline
                className="h-full w-full object-cover"
                onEnded={handleVideoEnded}
              />
            ) : avatarUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={avatarUrl} alt="Persona Avatar" className="h-full w-full object-cover" />
            ) : (
              <div className="flex h-full flex-col items-center justify-center text-gray-400">
                <svg className="h-16 w-16 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                </svg>
                <span className="text-sm">Avatar will appear when session starts</span>
              </div>
            )}
          </div>
          
          {/* Hidden audio element for TTS playback */}
          <audio ref={audioRef} className="hidden" onEnded={() => setAvatarState("idle")} />
          
          {/* Controls */}
          <div className="flex gap-3">
            {!recording ? (
              <button 
                onClick={startRecording} 
                className="flex items-center gap-2 rounded-lg bg-black px-5 py-2.5 text-white hover:bg-gray-800 transition-colors"
              >
                <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z"/>
                  <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/>
                </svg>
                Start Speaking
              </button>
            ) : (
              <button 
                onClick={stopRecording} 
                className="flex items-center gap-2 rounded-lg bg-red-600 px-5 py-2.5 text-white hover:bg-red-500 transition-colors animate-pulse"
              >
                <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 24 24">
                  <rect x="6" y="6" width="12" height="12" rx="2"/>
                </svg>
                Stop Recording
              </button>
            )}
            <button 
              onClick={completeSession} 
              className="rounded-lg border border-gray-300 px-5 py-2.5 text-gray-800 hover:bg-gray-50 transition-colors"
            >
              Complete Session
            </button>
          </div>
        </div>
        
        {/* Transcript Panel */}
        <div>
          <div className="rounded-lg border border-gray-200 bg-white shadow-sm">
            <div className="border-b border-gray-200 px-4 py-3">
              <h3 className="font-medium text-gray-900">Conversation</h3>
            </div>
            <div className="max-h-96 overflow-y-auto p-4 space-y-3">
              {transcript.length === 0 ? (
                <p className="text-sm text-gray-500 text-center py-4">
                  Start speaking to begin the conversation...
                </p>
              ) : (
                transcript.map((entry, idx) => (
                  <div 
                    key={idx} 
                    className={`rounded-lg p-3 text-sm ${
                      entry.role === "user" 
                        ? "bg-blue-50 text-blue-900 ml-4" 
                        : "bg-gray-100 text-gray-900 mr-4"
                    }`}
                  >
                    <div className="font-medium text-xs mb-1 opacity-70">
                      {entry.role === "user" ? "You" : personaInfo?.displayName || "Customer"}
                    </div>
                    {entry.content}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
