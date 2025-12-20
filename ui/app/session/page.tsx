"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import PulseProgressBar from "@/components/SbnProgressBar";
import { useSession, AvatarState } from "@/components/SessionContext";
import { useRouter } from "next/navigation";
import { useAvatarSpeech } from "@/hooks/useAvatarSpeech";
import { useSpeechRecognition } from "@/hooks/useSpeechRecognition";

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
  
  const [transcript, setTranscript] = useState<TranscriptEntry[]>([]);
  const [currentVideoSrc, setCurrentVideoSrc] = useState<string | null>(null);
  const [useStreamingAvatar, setUseStreamingAvatar] = useState(true);
  const [interimTranscript, setInterimTranscript] = useState("");
  const [isProcessing, setIsProcessing] = useState(false);
  const fallbackVideoRef = useRef<HTMLVideoElement | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  
  // Pre-flight check state
  const [sessionReady, setSessionReady] = useState(false);
  const [preflightStatus, setPreflightStatus] = useState<{
    avatar: "pending" | "connecting" | "ready" | "error";
    session: "pending" | "ready" | "error";
  }>({ avatar: "pending", session: "pending" });
  
  // Speech queue for buffering responses until avatar is connected
  const speechQueueRef = useRef<Array<{ text: string; emotion: string }>>([]);
  const isProcessingQueueRef = useRef(false);

  // Azure Speech Avatar hook for real-time streaming
  const {
    videoRef: avatarVideoRef,
    state: avatarSpeechState,
    isConnected: isAvatarConnected,
    isSpeaking: isAvatarSpeaking,
    avatarConfig,
    connect: connectAvatar,
    disconnect: disconnectAvatar,
    speak: speakWithAvatar,
    stopSpeaking,
    error: avatarError,
  } = useAvatarSpeech({
    persona: personaInfo?.type || "Relater",
    onStateChange: (state) => {
      if (state === "speaking") setAvatarState("speaking");
      else if (state === "connected") {
        setAvatarState("idle");
        setPreflightStatus(prev => ({ ...prev, avatar: "ready" }));
        console.log("[Session] Pre-flight: Avatar ready");
      }
      else if (state === "connecting") {
        setAvatarState("thinking");
        setPreflightStatus(prev => ({ ...prev, avatar: "connecting" }));
      }
    },
    onError: (err) => {
      console.error("[Session] Avatar error:", err);
      setPreflightStatus(prev => ({ ...prev, avatar: "error" }));
      setUseStreamingAvatar(false);
    },
  });

  // Store connectAvatar in a ref to avoid dependency issues
  const connectAvatarRef = useRef(connectAvatar);
  connectAvatarRef.current = connectAvatar;
  
  // Track connection state in a ref to avoid closure issues in callbacks
  const isAvatarConnectedRef = useRef(isAvatarConnected);
  isAvatarConnectedRef.current = isAvatarConnected;

  // Connect streaming avatar when session starts (only once when conditions are met)
  const hasAttemptedConnection = useRef(false);
  useEffect(() => {
    if (sessionId && useStreamingAvatar && !isAvatarConnected && avatarSpeechState === "idle" && !hasAttemptedConnection.current) {
      hasAttemptedConnection.current = true;
      console.log("[Session] Pre-flight: Starting avatar connection...");
      setPreflightStatus(prev => ({ ...prev, avatar: "connecting" }));
      connectAvatarRef.current();
    }
  }, [sessionId, useStreamingAvatar, isAvatarConnected, avatarSpeechState]);

  // Mark session as ready when sessionId exists
  useEffect(() => {
    if (sessionId) {
      setPreflightStatus(prev => ({ ...prev, session: "ready" }));
      console.log("[Session] Pre-flight: Session ready");
    }
  }, [sessionId]);

  // Check if all pre-flight checks pass
  useEffect(() => {
    const avatarReady = preflightStatus.avatar === "ready" || preflightStatus.avatar === "error"; // error means fallback mode
    const sessionOk = preflightStatus.session === "ready";
    
    if (avatarReady && sessionOk && !sessionReady) {
      console.log("[Session] Pre-flight: All checks passed, session ready to start");
      setSessionReady(true);
    }
  }, [preflightStatus, sessionReady]);

  // Initialize with intro video if available (fallback mode)
  useEffect(() => {
    if (!useStreamingAvatar && avatarVideoUrl && !currentVideoSrc) {
      setCurrentVideoSrc(avatarVideoUrl);
    }
  }, [avatarVideoUrl, currentVideoSrc, useStreamingAvatar]);

  // Store disconnectAvatar in a ref for cleanup
  const disconnectAvatarRef = useRef(disconnectAvatar);
  disconnectAvatarRef.current = disconnectAvatar;

  // Cleanup on unmount (empty deps - only runs on unmount)
  useEffect(() => {
    return () => {
      // Force disconnect on actual unmount
      disconnectAvatarRef.current(true);
    };
  }, []);

  // Process queued speech when avatar becomes connected
  const processQueueRef = useRef<() => Promise<void>>();
  processQueueRef.current = async () => {
    if (isProcessingQueueRef.current || !isAvatarConnected) return;
    if (speechQueueRef.current.length === 0) return;
    
    isProcessingQueueRef.current = true;
    console.log("[Session] Processing speech queue, items:", speechQueueRef.current.length);
    
    while (speechQueueRef.current.length > 0 && isAvatarConnected) {
      const item = speechQueueRef.current.shift();
      if (item) {
        console.log("[Session] Speaking queued item:", item.text.substring(0, 30) + "...");
        try {
          await speakWithAvatar(item.text, item.emotion);
        } catch (err) {
          console.error("[Session] Error speaking queued item:", err);
        }
      }
    }
    
    isProcessingQueueRef.current = false;
  };

  // When avatar connects, process any queued speech
  useEffect(() => {
    if (isAvatarConnected && speechQueueRef.current.length > 0) {
      console.log("[Session] Avatar connected, processing queued speech...");
      processQueueRef.current?.();
    }
  }, [isAvatarConnected]);

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

  // Send user text to backend and get AI response
  const sendUserMessage = useCallback(async (userText: string) => {
    console.log("[Session] sendUserMessage called with:", userText.substring(0, 50) + "...");
    if (!userText.trim() || !sessionId) {
      console.log("[Session] Skipping - no text or sessionId");
      return;
    }
    
    setIsProcessing(true);
    setAvatarState("thinking");
    
    // Add user message to transcript immediately
    setTranscript((t) => [...t, {
      role: "user",
      content: userText,
      timestamp: new Date().toISOString(),
    }]);

    console.log("[Session] Sending chat request to backend...");
    try {
      // Send text directly to a new text-based endpoint (faster than audio)
      const res = await fetch("/api/orchestrator/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sessionId,
          message: userText,
          persona: personaInfo?.type || "Relater",
        }),
      });
      
      if (!res.ok) throw new Error(`Chat request failed: ${res.status}`);
      
      const data = await res.json();
      console.log("[Session] Chat response received:", data.aiResponse?.substring(0, 50) + "...");
      
      // Add AI response to transcript
      if (data.aiResponse) {
        setTranscript((t) => [...t, {
          role: "assistant",
          content: String(data.aiResponse),
          timestamp: new Date().toISOString(),
        }]);
        
        // Use streaming avatar to speak the response
        const emotion = data.avatarEmotion || data.emotion || "neutral";
        // Use ref to get current connection state (avoids closure issues)
        const currentlyConnected = isAvatarConnectedRef.current;
        console.log("[Session] Avatar state check - useStreamingAvatar:", useStreamingAvatar, "isAvatarConnected:", currentlyConnected, "hasAttemptedConnection:", hasAttemptedConnection.current);
        
        if (useStreamingAvatar) {
          if (currentlyConnected) {
            // Avatar is ready, speak immediately
            console.log("[Session] Calling speakWithAvatar with emotion:", emotion);
            await speakWithAvatar(data.aiResponse, emotion);
          } else if (hasAttemptedConnection.current) {
            // Avatar connection was attempted but not ready yet, queue the speech
            console.log("[Session] Avatar connection in progress, queuing speech for later");
            speechQueueRef.current.push({ text: data.aiResponse, emotion });
          } else {
            // Avatar not available, use fallback
            console.log("[Session] Avatar not available, using fallback");
            if (data.audioBase64) {
              setAvatarState("speaking");
              const audioBlob = await fetch(`data:audio/mpeg;base64,${data.audioBase64}`).then(r => r.blob());
              await playAudioBlob(audioBlob);
            }
          }
        } else {
          // Streaming avatar disabled, use fallback
          console.log("[Session] Streaming avatar disabled, using fallback");
          if (data.audioBase64) {
            setAvatarState("speaking");
            const audioBlob = await fetch(`data:audio/mpeg;base64,${data.audioBase64}`).then(r => r.blob());
            await playAudioBlob(audioBlob);
          }
        }
      }
      
      setAvatarState("idle");
    } catch (e) {
      console.error("[Session] Chat request failed:", e);
      setAvatarState("idle");
    } finally {
      setIsProcessing(false);
    }
  }, [sessionId, personaInfo, useStreamingAvatar, speakWithAvatar, setAvatarState, playAudioBlob]);

  // Streaming speech recognition hook - natural conversation without push-to-talk
  const {
    state: recognitionState,
    isListening,
    interimText,
    startListening,
    stopListening,
    error: recognitionError,
  } = useSpeechRecognition({
    onInterimResult: (text) => {
      setInterimTranscript(text);
    },
    onFinalResult: (text) => {
      console.log("[Session] Final speech result:", text);
      setInterimTranscript("");
      sendUserMessage(text);
    },
    onSpeechStart: () => {
      console.log("[Session] User started speaking");
      setAvatarState("listening");
    },
    onSpeechEnd: () => {
      console.log("[Session] User stopped speaking");
    },
    onError: (err) => {
      console.error("[Session] Speech recognition error:", err);
    },
    silenceTimeoutMs: 1500, // 1.5 seconds of silence triggers processing
  });

  // Store sendUserMessage in ref for the hook
  const sendUserMessageRef = useRef(sendUserMessage);
  sendUserMessageRef.current = sendUserMessage;

  const completeSession = async () => {
    if (!sessionId) return;
    stopListening();
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
            
            {/* Streaming Avatar (Azure Speech Avatar via WebRTC) */}
            {useStreamingAvatar && (
              <video
                ref={avatarVideoRef}
                autoPlay
                playsInline
                muted={false}
                className={`absolute inset-0 h-full w-full object-cover ${isAvatarConnected ? "z-10" : "z-0 opacity-0"}`}
              />
            )}
            
            {/* Persona image - shown as fallback when avatar not connected */}
            {avatarUrl && (
              // eslint-disable-next-line @next/next/no-img-element
              <img 
                src={avatarUrl} 
                alt="Persona Avatar" 
                className={`absolute inset-0 h-full w-full object-cover ${isAvatarConnected ? "z-0" : "z-10"}`}
              />
            )}
            
            {/* Fallback: Pre-generated video */}
            {currentVideoSrc && !useStreamingAvatar && (
              <video
                ref={fallbackVideoRef}
                src={currentVideoSrc}
                autoPlay
                playsInline
                className="absolute inset-0 h-full w-full object-cover z-10"
                onEnded={handleVideoEnded}
              />
            )}
            
            {/* Placeholder when no avatar image available */}
            {!avatarUrl && !currentVideoSrc && (
              <div className="flex h-full flex-col items-center justify-center text-gray-400">
                <svg className="h-16 w-16 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                </svg>
                <span className="text-sm">
                  {avatarSpeechState === "connecting" ? "Connecting avatar..." : "Avatar will appear when session starts"}
                </span>
              </div>
            )}
            
            {/* Avatar connection status indicator */}
            {useStreamingAvatar && avatarSpeechState === "connecting" && (
              <div className="absolute inset-0 flex items-center justify-center bg-gray-900/80">
                <div className="text-center text-white">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-white mx-auto mb-2"></div>
                  <span className="text-sm">Connecting avatar...</span>
                </div>
              </div>
            )}
            
            {/* Avatar error indicator */}
            {avatarError && (
              <div className="absolute bottom-2 left-2 right-2 bg-red-500/90 text-white text-xs px-2 py-1 rounded">
                Avatar unavailable: Using fallback mode
              </div>
            )}
          </div>
          
          {/* Hidden audio element for TTS playback */}
          <audio ref={audioRef} className="hidden" onEnded={() => setAvatarState("idle")} />
          
          {/* Pre-flight Status Panel */}
          {!sessionReady && (
            <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 mb-4">
              <h4 className="font-medium text-gray-900 mb-3">Preparing Session...</h4>
              <div className="space-y-2">
                <div className="flex items-center gap-2 text-sm">
                  {preflightStatus.session === "ready" ? (
                    <svg className="h-5 w-5 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                  ) : (
                    <div className="h-5 w-5 animate-spin rounded-full border-2 border-gray-300 border-t-blue-500"></div>
                  )}
                  <span className={preflightStatus.session === "ready" ? "text-green-700" : "text-gray-600"}>
                    Session initialized
                  </span>
                </div>
                <div className="flex items-center gap-2 text-sm">
                  {preflightStatus.avatar === "ready" ? (
                    <svg className="h-5 w-5 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                  ) : preflightStatus.avatar === "error" ? (
                    <svg className="h-5 w-5 text-yellow-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>
                  ) : (
                    <div className="h-5 w-5 animate-spin rounded-full border-2 border-gray-300 border-t-blue-500"></div>
                  )}
                  <span className={
                    preflightStatus.avatar === "ready" ? "text-green-700" : 
                    preflightStatus.avatar === "error" ? "text-yellow-700" : "text-gray-600"
                  }>
                    {preflightStatus.avatar === "ready" ? "Avatar connected" : 
                     preflightStatus.avatar === "error" ? "Avatar unavailable (using fallback)" :
                     preflightStatus.avatar === "connecting" ? "Connecting avatar..." : "Waiting for avatar..."}
                  </span>
                </div>
              </div>
            </div>
          )}
          
          {/* Controls */}
          <div className="flex flex-col gap-3">
            <div className="flex gap-3">
              {!isListening ? (
                <button 
                  onClick={startListening} 
                  disabled={isProcessing || !sessionReady}
                  className="flex items-center gap-2 rounded-lg bg-black px-5 py-2.5 text-white hover:bg-gray-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {!sessionReady ? (
                    <div className="h-5 w-5 animate-spin rounded-full border-2 border-gray-400 border-t-white"></div>
                  ) : (
                    <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z"/>
                      <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/>
                    </svg>
                  )}
                  {sessionReady ? "Start Conversation" : "Preparing..."}
                </button>
              ) : (
                <button 
                  onClick={stopListening} 
                  className="flex items-center gap-2 rounded-lg bg-green-600 px-5 py-2.5 text-white hover:bg-green-500 transition-colors"
                >
                  <svg className="h-5 w-5 animate-pulse" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z"/>
                    <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/>
                  </svg>
                  Listening... (click to stop)
                </button>
              )}
              <button 
                onClick={completeSession} 
                className="rounded-lg border border-gray-300 px-5 py-2.5 text-gray-800 hover:bg-gray-50 transition-colors"
              >
                Complete Session
              </button>
            </div>
            
            {/* Interim transcript display */}
            {interimTranscript && (
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-sm text-blue-800">
                <span className="font-medium">You&apos;re saying: </span>
                {interimTranscript}
              </div>
            )}
            
            {/* Processing indicator */}
            {isProcessing && (
              <div className="flex items-center gap-2 text-sm text-gray-600">
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-gray-600"></div>
                Processing your message...
              </div>
            )}
            
            {/* Recognition error */}
            {recognitionError && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-800">
                Speech recognition error: {recognitionError.message}
              </div>
            )}
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
