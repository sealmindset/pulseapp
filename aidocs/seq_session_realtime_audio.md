# Sequence Diagram — Session Realtime Audio & Avatar

```mermaid
sequenceDiagram
    autonumber
    participant U as User
    participant UI as Browser UI (Session)
    participant MR as MediaRecorder
    participant API as Next.js Proxy (/api/orchestrator/audio/chunk)
    participant FA as Function App (Orchestrator)
    participant ASR as Azure OpenAI (ASR/Realtime)
    participant TTS as Azure OpenAI (TTS)

    U->>UI: Click "Start Mic"
    UI->>UI: getUserMedia({ audio:true })
    UI->>MR: start(timeslice=1000ms)
    note right of UI: Avatar renders if avatarUrl was provided by start

    loop Every 1s chunk
        MR-->>UI: dataavailable(chunk)
        UI->>API: POST FormData{ sessionId, chunk }
        API->>FA: POST /audio/chunk
        FA->>ASR: Transcribe chunk
        ASR-->>FA: partial transcript
        FA->>TTS: Synthesize response (optional)
        TTS-->>FA: audio bytes or URL
        alt JSON payload
            FA-->>API: { partialTranscript, ttsUrl|audioBase64 }
            API-->>UI: same JSON
            UI->>UI: append partial transcript
            alt audioBase64 or URL
                UI->>UI: play audio via HTMLAudioElement
            else raw audio/*
                UI->>UI: play blob via HTMLAudioElement
            end
        else raw audio/*
            FA-->>API: audio/*
            API-->>UI: audio/*
            UI->>UI: play blob via HTMLAudioElement
        end
    end

    Note over FA,ASR,TTS: Private Endpoints + Private DNS; no public access
```
