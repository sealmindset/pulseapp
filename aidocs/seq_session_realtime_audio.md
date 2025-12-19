# Sequence Diagram — Session Realtime Audio & Avatar

This diagram illustrates the complete audio processing and avatar video generation flow using:
- **gpt-4o-realtime-preview** for Speech-to-Text (STT) and Text-to-Speech (TTS)
- **gpt-5-chat** for conversational AI responses
- **sora-2** for lip-synced avatar video generation (when available)

```mermaid
sequenceDiagram
    autonumber
    participant U as User
    participant UI as Browser UI (Session)
    participant MR as MediaRecorder
    participant API as Next.js Proxy (/api/orchestrator/audio/chunk)
    participant FA as Function App (Orchestrator)
    participant STT as Azure OpenAI (gpt-4o-realtime STT)
    participant LLM as Azure OpenAI (gpt-5-chat)
    participant TTS as Azure OpenAI (gpt-4o-realtime TTS)
    participant SORA as Azure OpenAI (sora-2)
    participant BLOB as Azure Blob Storage

    U->>UI: Click "Start Speaking"
    UI->>UI: getUserMedia({ audio:true })
    UI->>MR: start(timeslice=1000ms)
    UI->>UI: setAvatarState("listening")
    note right of UI: Avatar video plays if avatarVideoUrl was provided by session/start

    loop Every 1s chunk
        MR-->>UI: dataavailable(chunk)
        UI->>API: POST FormData{ sessionId, chunk }
        API->>FA: POST /audio/chunk
        
        rect rgb(240, 248, 255)
            Note over FA,BLOB: Step 1: Speech-to-Text
            FA->>STT: transcribe_audio(chunk, format="webm")
            STT-->>FA: transcript text
        end
        
        rect rgb(255, 248, 240)
            Note over FA,BLOB: Step 2: Load Context & Generate Response
            FA->>BLOB: read conversation history
            BLOB-->>FA: previous messages[]
            FA->>LLM: generate_conversation_response(transcript, persona, history)
            LLM-->>FA: AI response text
            FA->>BLOB: save updated conversation history
        end
        
        rect rgb(240, 255, 240)
            Note over FA,TTS: Step 3: Text-to-Speech
            FA->>TTS: generate_speech(response, voice="alloy")
            TTS-->>FA: audio bytes (MP3)
        end
        
        rect rgb(255, 240, 255)
            Note over FA,SORA: Step 4: Avatar Video (when Sora-2 available)
            alt Sora-2 enabled
                FA->>FA: determine_emotion(response)
                FA->>SORA: generate_avatar_video(persona, response, emotion)
                SORA-->>FA: video bytes (MP4)
                FA->>BLOB: store video clip
                BLOB-->>FA: video URL
            end
        end
        
        FA-->>API: JSON response
        Note right of FA: { partialTranscript, aiResponse, audioBase64, avatarState, avatarVideo? }
        API-->>UI: same JSON
        
        UI->>UI: append user transcript to conversation
        UI->>UI: append AI response to conversation
        UI->>UI: setAvatarState("speaking")
        
        alt avatarVideo present
            UI->>UI: play video via HTMLVideoElement
        end
        
        alt audioBase64 present
            UI->>UI: play audio via HTMLAudioElement
        end
        
        UI->>UI: onAudioEnded → setAvatarState("idle")
    end

    U->>UI: Click "Stop Recording"
    UI->>MR: stop()
    UI->>UI: setAvatarState("idle")

    Note over FA,SORA: All Azure services accessed via Private Endpoints + Private DNS
```

## Response Payload Structure

```json
{
  "sessionId": "uuid",
  "partialTranscript": "What the user said",
  "aiResponse": "What the AI customer responds",
  "audioBase64": "base64-encoded MP3 audio",
  "avatarState": "speaking",
  "avatarVideo": {
    "url": "https://storage.blob.../video.mp4",
    "base64": "base64-encoded MP4 video (alternative)",
    "emotion": "interested"
  }
}
```

## Avatar States

| State | Indicator | Description |
|-------|-----------|-------------|
| `idle` | None | Avatar is waiting, no activity |
| `listening` | Blue pulsing dot | User is speaking, avatar is listening |
| `speaking` | Green pulsing dot | Avatar is speaking/playing audio |
| `thinking` | Yellow pulsing dot | Processing user input |

## Graceful Degradation

When components are unavailable:

1. **Sora-2 unavailable:** `avatarVideo` field omitted; UI shows static image or placeholder
2. **TTS fails:** `audioBase64` field omitted; transcript still displayed
3. **STT fails:** Returns `{ partialTranscript: null, message: "No speech detected" }`
4. **LLM fails:** Returns fallback response: "I'm sorry, I didn't catch that. Could you repeat?"
