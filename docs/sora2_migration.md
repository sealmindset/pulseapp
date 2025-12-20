# PULSE Platform: Avatar & Audio Pipeline Implementation

> **Date:** 2025-12-19  
> **Status:** Implementation Complete  
> **Region:** East US 2

## Executive Summary

This document outlines the implementation of the PULSE training platform's avatar and audio systems:

1. **Azure Speech Avatar** - Real-time lip-synced avatar via WebRTC streaming
2. **Audio Pipeline** - Full STT/LLM/TTS pipeline using Azure OpenAI models

### Key Changes
- **Avatar System:** Azure Speech Services Avatar (real-time WebRTC streaming)
- **Audio Pipeline:** Full STT/LLM/TTS pipeline with gpt-4o-realtime-preview
- **Models Deployed:** gpt-5-chat, o4-mini, gpt-4o-realtime-preview

### Why Azure Speech Avatar (Not Sora-2)
| Feature | Sora-2 | Azure Speech Avatar |
|---------|--------|---------------------|
| **Duration** | 12 seconds max | Unlimited (real-time) |
| **Latency** | High (video generation) | Low (WebRTC streaming) |
| **Lip-sync** | Post-generation | Real-time with TTS |
| **Use case** | Pre-rendered videos | Interactive conversations |
| **Production ready** | Limited preview | Generally available |

---

## 1. Architecture Overview

### 1.1 Azure Service Deployments

| Service | Resource | Purpose |
|---------|----------|---------|
| **Azure OpenAI** | Persona-Core-Chat (`gpt-5-chat`) | Conversational AI for verbal interactions |
| **Azure OpenAI** | Persona-High-Reasoning (`o4-mini`) | Complex reasoning (BCE/MCF/CPO agents) |
| **Azure OpenAI** | PULSE-Audio-Realtime (`gpt-4o-realtime-preview`) | Speech-to-text & text-to-speech |
| **Azure Speech** | Speech Services (S0) | Real-time avatar with WebRTC streaming |

### 1.2 Audio Processing Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           PULSE Training Session                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  User speaks into microphone                                                 │
│  └── MediaRecorder captures audio chunks (1 second intervals)               │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  POST /api/orchestrator/audio/chunk                                          │
│  └── FormData: { sessionId, chunk: audio.webm }                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Azure Function: audio_chunk                                                 │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ Step 1: Speech-to-Text (STT)                                         │   │
│  │ └── gpt-4o-realtime-preview → transcribe audio → text               │   │
│  ├──────────────────────────────────────────────────────────────────────┤   │
│  │ Step 2: Generate AI Response                                         │   │
│  │ └── gpt-5-chat → persona-aware conversation → response text         │   │
│  ├──────────────────────────────────────────────────────────────────────┤   │
│  │ Step 3: Text-to-Speech (TTS)                                         │   │
│  │ └── gpt-4o-realtime-preview → synthesize speech → MP3 audio         │   │
│  ├──────────────────────────────────────────────────────────────────────┤   │
│  │ Step 4: Avatar Video Generation (when Sora-2 available)              │   │
│  │ └── sora-2 → lip-synced video → MP4 video                           │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Response JSON:                                                              │
│  {                                                                           │
│    "sessionId": "uuid",                                                      │
│    "partialTranscript": "User's speech",                                    │
│    "aiResponse": "AI customer response",                                    │
│    "audioBase64": "...",           // TTS audio (MP3)                       │
│    "avatarState": "speaking",      // idle | speaking | listening           │
│    "avatarVideo": {                // Sora-2 video (when available)         │
│      "url": "https://...",                                                  │
│      "base64": "...",                                                       │
│      "emotion": "interested"                                                │
│    }                                                                         │
│  }                                                                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  UI Playback                                                                 │
│  ├── Play TTS audio via <audio> element                                     │
│  ├── Display avatar video via <video> element (or static image fallback)   │
│  ├── Update avatar state indicator (speaking/listening/idle)               │
│  └── Append transcript entries to conversation panel                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. File Changes Summary

### 2.1 New Files Created

| File | Description |
|------|-------------|
| `orchestrator/shared_code/openai_client.py` | Unified Azure OpenAI client for chat completion, STT, and TTS |
| `orchestrator/shared_code/avatar_service.py` | Sora-2 video generation service with persona configurations |

### 2.2 Modified Files

| File | Changes |
|------|---------|
| `orchestrator/audio_chunk/__init__.py` | Full STT → LLM → TTS → Avatar pipeline implementation |
| `orchestrator/session_start/__init__.py` | Intro avatar video generation, enhanced response format |
| `ui/components/SessionContext.tsx` | Added `avatarVideoUrl`, `avatarState`, `personaInfo` state |
| `ui/app/session/page.tsx` | Video player, state indicators, enhanced transcript UI |
| `ui/app/page.tsx` | Handle new session start response format |
| `variables.tf` | Updated `openai_model_visual_asset_id` to `sora-2` |
| `aidocs/aiworkflow.md` | Updated data contracts for new response formats |
| `CHANGELOG.md` | Comprehensive entry for all changes |

---

## 3. Backend Implementation Details

### 3.1 OpenAI Client (`orchestrator/shared_code/openai_client.py`)

Provides unified access to all Azure OpenAI deployments:

```python
# Chat completion (gpt-5-chat or o4-mini)
response = chat_completion(
    messages=[{"role": "user", "content": "Hello"}],
    deployment_key="deployment_core_chat",  # or "deployment_high_reasoning"
    temperature=0.7,
)

# Speech-to-text (gpt-4o-realtime-preview)
transcript = transcribe_audio(audio_data, audio_format="webm")

# Text-to-speech (gpt-4o-realtime-preview)
audio_bytes = generate_speech(text, voice="alloy", speed=1.0)

# Conversational response with persona
response = generate_conversation_response(
    user_message="Tell me about your products",
    persona_type="Director",
    conversation_history=[...],
)
```

### 3.2 Avatar Service (`orchestrator/shared_code/avatar_service.py`)

Manages Sora-2 video generation with persona-specific configurations:

```python
# Check if Sora-2 is available
if is_avatar_service_available():
    # Generate lip-synced avatar video
    result = generate_avatar_video(
        persona_type="Director",
        speech_text="I need to see results quickly.",
        emotion="interested",
        duration_seconds=5.0,
        session_id="uuid",
    )
    # result contains: video_url, video_base64, duration, persona, emotion

# Generate intro video for session start
intro = generate_intro_avatar(persona_type="Socializer", session_id="uuid")
```

#### Persona Avatar Configurations

| Persona | Appearance | Setting | Demeanor |
|---------|------------|---------|----------|
| **Director** | Professional executive, confident posture | Formal office | Assertive, time-conscious |
| **Relater** | Warm friendly person, relaxed posture | Home/cafe | Patient, empathetic |
| **Socializer** | Energetic expressive, animated gestures | Vibrant colorful | Enthusiastic, talkative |
| **Thinker** | Thoughtful analytical, measured movements | Organized workspace | Careful, methodical |

#### Emotion Expressions

| Emotion | Visual Expression |
|---------|-------------------|
| `neutral` | Calm neutral expression, attentive listening |
| `interested` | Raised eyebrows, leaning forward, engaged |
| `skeptical` | Slight frown, crossed arms, questioning |
| `pleased` | Warm smile, relaxed posture, nodding |
| `concerned` | Furrowed brow, thoughtful, head tilt |
| `excited` | Bright smile, animated gestures |
| `hesitant` | Uncertain expression, considering look |

### 3.3 Audio Chunk Handler (`orchestrator/audio_chunk/__init__.py`)

Complete pipeline implementation:

1. **Receive audio chunk** from UI via FormData
2. **Transcribe** using `gpt-4o-realtime-preview`
3. **Load conversation history** from blob storage
4. **Generate AI response** using `gpt-5-chat` with persona context
5. **Save updated conversation** to blob storage
6. **Generate TTS audio** using `gpt-4o-realtime-preview`
7. **Generate avatar video** using Sora-2 (when available)
8. **Return combined response** to UI

### 3.4 Session Start Handler (`orchestrator/session_start/__init__.py`)

Enhanced to support video avatars:

```python
# New response format
{
    "sessionId": "uuid",
    "persona": {
        "type": "Director",
        "displayName": "The Director"
    },
    "avatarUrl": null,              # Static image fallback
    "avatarVideoUrl": "https://...", # Sora-2 intro video
    "avatarVideoBase64": "...",      # Alternative: base64 video
    "avatarEmotion": "neutral"       # Initial emotion state
}
```

---

## 4. Frontend Implementation Details

### 4.1 Session Context (`ui/components/SessionContext.tsx`)

New state fields added:

```typescript
export type AvatarState = "idle" | "speaking" | "listening" | "thinking";

export type PersonaInfo = {
  type: string;
  displayName: string;
};

type SessionState = {
  // Existing fields...
  avatarVideoUrl: string | null;    // Sora-2 video URL
  avatarState: AvatarState;         // Current avatar state
  personaInfo: PersonaInfo | null;  // Persona metadata
  // Setters...
  setAvatarVideoUrl: (u: string | null) => void;
  setAvatarState: (s: AvatarState) => void;
  setPersonaInfo: (info: PersonaInfo | null) => void;
};
```

### 4.2 Session Page (`ui/app/session/page.tsx`)

Key UI enhancements:

1. **Video Player:** Replaces static `<img>` with `<video>` element
2. **State Indicators:** Animated dots showing speaking/listening/thinking
3. **Transcript Panel:** Role-based styling (user vs assistant messages)
4. **Audio Element:** Hidden `<audio>` for TTS playback management

```tsx
// Avatar display with video support
{currentVideoSrc ? (
  <video
    ref={videoRef}
    src={currentVideoSrc}
    autoPlay
    playsInline
    onEnded={handleVideoEnded}
  />
) : avatarUrl ? (
  <img src={avatarUrl} alt="Persona Avatar" />
) : (
  <div>Avatar will appear when session starts</div>
)}
```

### 4.3 Pre-Session Page (`ui/app/page.tsx`)

Updated to handle new session start response:

```typescript
const json = await res.json();
setSessionId(json.sessionId);

// Handle avatar video URL (Sora-2)
if (json.avatarVideoUrl) {
  setAvatarVideoUrl(json.avatarVideoUrl);
}

// Handle persona info
if (json.persona && typeof json.persona === "object") {
  setPersonaInfo({
    type: json.persona.type,
    displayName: json.persona.displayName,
  });
}
```

---

## 5. Environment Variables

### 5.1 Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `OPENAI_ENDPOINT` | Azure OpenAI endpoint URL | `https://xxx.openai.azure.com` |
| `AZURE_OPENAI_API_KEY` | Azure OpenAI API key | `xxxxxxxx` |
| `OPENAI_API_VERSION` | API version | `2024-12-01-preview` |
| `OPENAI_DEPLOYMENT_PERSONA_CORE_CHAT` | Chat deployment name | `Persona-Core-Chat` |
| `OPENAI_DEPLOYMENT_PERSONA_HIGH_REASONING` | Reasoning deployment | `Persona-High-Reasoning` |
| `OPENAI_DEPLOYMENT_PULSE_AUDIO_REALTIME` | Audio deployment | `PULSE-Audio-Realtime` |
| `OPENAI_DEPLOYMENT_PERSONA_VISUAL_ASSET` | Visual asset deployment | `Persona-Visual-Asset` |

### 5.2 Feature Flags

| Variable | Default | Description |
|----------|---------|-------------|
| `TRAINING_ORCHESTRATOR_ENABLED` | `false` | Enable training orchestrator endpoints |
| `AUDIO_PROCESSING_ENABLED` | `true` | Enable STT/TTS processing |

---

## 6. Terraform Configuration

### 6.1 Key Variables (`variables.tf`)

```hcl
variable "openai_model_visual_asset_id" {
  type        = string
  description = "Model ID for Persona-Visual-Asset deployment (sora-2 for avatar video generation)."
  default     = "sora-2"
}

variable "enable_visual_asset_deployment" {
  type        = bool
  description = "Whether to deploy the visual asset (Sora-2) model for avatar video generation."
  default     = true
}
```

### 6.2 Current Deployment Status (`prod.tfvars`)

```hcl
location = "eastus2"

# Deployed and active
# - Persona-Core-Chat (gpt-5-chat)
# - Persona-High-Reasoning (o4-mini)
# - PULSE-Audio-Realtime (gpt-4o-realtime-preview)

# Pending quota approval
enable_app_service             = false  # Requires Premium V3 quota
enable_visual_asset_deployment = false  # Requires Sora-2 access
```

---

## 7. Pending Actions

### 7.1 Azure Quota Requests

| Request | Region | Status | Impact |
|---------|--------|--------|--------|
| Premium V3 VM quota | East US 2 | Pending | Enables App Service deployment |
| Sora-2 model access | Subscription | Pending | Enables avatar video generation |

### 7.2 Enabling After Quota Approval

Once quotas are approved, update `prod.tfvars`:

```hcl
enable_app_service             = true
enable_visual_asset_deployment = true
```

Then apply:

```bash
cd /path/to/pulseapp
terraform apply -var-file=prod.tfvars
```

---

## 8. Testing

### 8.1 Local Testing (Without Sora-2)

The system gracefully degrades when Sora-2 is unavailable:

1. Audio processing (STT/TTS) works independently
2. Avatar service returns placeholder response
3. UI falls back to static image or placeholder

### 8.2 Verifying Audio Pipeline

```bash
# Start Function App locally
cd orchestrator
func start

# Test audio chunk endpoint
curl -X POST http://localhost:7071/api/audio/chunk \
  -F "sessionId=test-session" \
  -F "chunk=@test-audio.webm"
```

### 8.3 Verifying Session Start

```bash
curl -X POST http://localhost:7071/api/session/start \
  -H "Content-Type: application/json" \
  -d '{"persona": "Director"}'
```

---

## 9. Rollback Procedure

If issues arise, revert to DALL-E-3 configuration:

1. Update `variables.tf`:
   ```hcl
   variable "openai_model_visual_asset_id" {
     default = "dall-e-3"
   }
   ```

2. Update `prod.tfvars`:
   ```hcl
   enable_visual_asset_deployment = false
   ```

3. The UI will automatically fall back to static images when video is unavailable.

---

## 10. Future Enhancements

1. **Video Caching:** Cache generated avatar videos to reduce latency
2. **Streaming Video:** Implement video streaming for longer responses
3. **Emotion Detection:** Use LLM to detect emotion from response content
4. **Avatar Customization:** Allow persona appearance customization
5. **Lip-Sync Optimization:** Fine-tune video generation prompts for better sync
