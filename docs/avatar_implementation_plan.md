# PULSE Interactive Avatar Implementation Plan

**Date:** 2025-12-19
**Status:** ✅ Phase 1, 2, & 3 Complete - Avatar Integration Deployed

---

## Executive Summary

The PULSE training platform requires real-time interactive avatars that respond to voice input. The backend orchestrator endpoints already exist and are functional. The primary gap is **client-side Azure Speech Avatar WebRTC integration** for lip-synced video streaming.

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Fallback when avatar unavailable** | Static image + audio (TTS) | Ensures demo can proceed even if avatar service fails |
| **Token refresh approach** | Proactive (before expiry) | Prevents mid-conversation interruptions |
| **Audio handling** | Keep backend TTS as fallback | Dual-path ensures reliability |

---

## Current State

### What Exists and Works

| Component | Location | Status |
|-----------|----------|--------|
| Orchestrator `/session/start` | `orchestrator/session_start/` | Implemented |
| Orchestrator `/audio/chunk` | `orchestrator/audio_chunk/` | Implemented (STT → LLM → TTS) |
| Orchestrator `/session/complete` | `orchestrator/session_complete/` | Implemented |
| Orchestrator `/feedback/{sessionId}` | `orchestrator/feedback_session/` | Implemented |
| `transcribe_audio()` | `orchestrator/shared_code/openai_client.py` | Implemented |
| `generate_speech()` | `orchestrator/shared_code/openai_client.py` | Implemented |
| `generate_conversation_response()` | `orchestrator/shared_code/openai_client.py` | Implemented |
| Avatar service config | `orchestrator/shared_code/avatar_service.py` | Implemented |
| Azure Speech module | `modules/speech/` | Deployed |
| UI Session page | `ui/app/session/page.tsx` | Exists (needs avatar integration) |

### What's Missing

| Component | Description | Status |
|-----------|-------------|--------|
| `AZURE_SPEECH_KEY` in Function App | Environment variable not wired through Terraform | ✅ **DONE** (2025-12-19) |
| `/avatar/token` endpoint | Client needs auth token for Speech SDK | ❌ Pending |
| Speech SDK in UI | `microsoft-cognitiveservices-speech-sdk` npm package | ❌ Pending |
| `useAvatarSpeech` hook | React hook for WebRTC avatar streaming | ❌ Pending |
| Session page avatar integration | Connect hook to existing UI | ❌ Pending |

### Completed Since Initial Planning (2025-12-19)

| Component | Location | Notes |
|-----------|----------|-------|
| Speech key Terraform output | `modules/speech/outputs.tf` | `speech_key` output added |
| Speech key variable in app module | `modules/app/variables.tf` | `speech_key` variable added |
| Speech key in Function App settings | `modules/app/main.tf` | `AZURE_SPEECH_KEY` added to app_settings |
| Speech key wiring in main.tf | `main.tf` | Passes `speech_key = module.speech.speech_key` |
| `get_avatar_token()` function | `avatar_service.py:242-280` | Returns token, region, ICE servers |
| `get_avatar_config()` function | `avatar_service.py:93-118` | Returns persona-specific avatar config |
| `get_ice_server_info()` function | `avatar_service.py:221-239` | Gets WebRTC ICE server info |
| AI capacity increased | `prod.tfvars` | Core: 50, Reasoning: 20, Audio: 4 |
| Function App deployed | Azure | With TRAINING_ORCHESTRATOR_ENABLED=true |

---

## Implementation Phases

### Phase 1: Infrastructure & Configuration ✅ COMPLETE

**Effort:** Small | **Risk:** Low | **Dependencies:** None | **Completed:** 2025-12-19

> **All Phase 1 tasks have been completed.** The Terraform configuration now automatically provisions the Speech key to the Function App.

#### 1.1 Expose Speech Key from Module ✅

**File:** `modules/speech/outputs.tf` - Already implemented as `speech_key`

#### 1.2 Wire Speech Key to Function App ✅

- `modules/app/variables.tf` - `speech_key` variable added
- `modules/app/main.tf` - `AZURE_SPEECH_KEY` added to app_settings
- `main.tf` - Passes `speech_key = module.speech.speech_key`

**Additional settings added to Function App:**
- `TRAINING_ORCHESTRATOR_ENABLED = true`
- `PROMPTS_CONTAINER` = interaction-logs container
- `SCM_DO_BUILD_DURING_DEPLOYMENT = true`
- `ENABLE_ORYX_BUILD = true`

---

### Phase 2: Backend Avatar Token Endpoint ✅ COMPLETE

**Effort:** Small | **Risk:** Medium | **Dependencies:** Phase 1 ✅ | **Completed:** 2025-12-19

> **All Phase 2 tasks completed.** The avatar token endpoint is deployed and returning valid tokens.

#### 2.1 Create Avatar Token Function ✅ DONE

**New File:** `orchestrator/avatar_token/__init__.py`

```python
"""
Avatar token handler - provides authentication for client-side Speech SDK.
Returns token, region, ICE servers, and avatar configuration.
"""
import logging
import os
import azure.functions as func
from shared_code.avatar_service import get_avatar_token, get_avatar_config
from shared_code.http import json_ok, no_content, text_error

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}

def main(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return no_content(headers=CORS_HEADERS)

    if not os.getenv("TRAINING_ORCHESTRATOR_ENABLED", "").lower() in ("true", "1"):
        return text_error("Disabled", 503, headers=CORS_HEADERS)

    try:
        body = req.get_json()
    except:
        body = {}

    persona_type = body.get("persona", "Relater")

    token_info = get_avatar_token()
    if not token_info:
        return text_error("Avatar service unavailable", 503, headers=CORS_HEADERS)

    avatar_config = get_avatar_config(persona_type)

    return json_ok({
        "token": token_info["token"],
        "region": token_info["region"],
        "iceServers": token_info.get("ice_servers"),
        "expiresIn": token_info.get("expires_in", 600),
        "avatarConfig": avatar_config,
    }, headers=CORS_HEADERS)
```

**New File:** `orchestrator/avatar_token/function.json`

```json
{
  "bindings": [
    {
      "authLevel": "anonymous",
      "type": "httpTrigger",
      "direction": "in",
      "name": "req",
      "methods": ["post", "options"],
      "route": "avatar/token"
    },
    {
      "type": "http",
      "direction": "out",
      "name": "$return"
    }
  ]
}
```

#### 2.2 Create UI Proxy Route ✅ DONE

**File Created:** `ui/app/api/orchestrator/avatar/token/route.ts`

Standard proxy pattern matching existing routes.

#### 2.3 Enable Speech Services Public Access ✅ DONE

Speech Services required public network access to be enabled for token endpoint.
```bash
az rest --method PATCH --uri ".../speech-pulse-training-prod?api-version=2023-05-01" \
  --body '{"properties":{"publicNetworkAccess":"Enabled"}}'
```

**Test Result (2025-12-19):**
```bash
curl -X POST "https://func-pulse-training-scenario-prod.azurewebsites.net/api/avatar/token" \
  -H "Content-Type: application/json" -d '{"persona":"Director"}'
# Returns: token, region, iceServers, expiresIn, avatarConfig
```

---

### Phase 3: UI Speech SDK Integration (Core Feature) ✅ COMPLETE

**Effort:** Large | **Risk:** High | **Dependencies:** Phase 2 ✅ | **Completed:** 2025-12-19

#### 3.1 Install Speech SDK ✅ DONE

```bash
cd ui && npm install microsoft-cognitiveservices-speech-sdk
```

#### 3.2 Create Avatar Hook ✅ DONE

**File Created:** `ui/hooks/useAvatarSpeech.ts`

Key responsibilities:
- Fetch token from `/api/orchestrator/avatar/token`
- Initialize Speech SDK with avatar config
- Establish WebRTC peer connection
- Handle video stream to `<video>` element
- Provide `speak(text, emotion)` method
- Implement proactive token refresh (before 10min expiry)
- Graceful fallback to static image on error

```typescript
interface UseAvatarSpeechReturn {
  videoRef: React.RefObject<HTMLVideoElement>;
  state: "idle" | "speaking" | "listening" | "connecting" | "error";
  isConnected: boolean;
  connect: () => Promise<void>;
  disconnect: () => void;
  speak: (text: string, emotion?: string) => Promise<void>;
  stopSpeaking: () => void;
}
```

#### 3.3 Update Session Page ✅ DONE

**File Modified:** `ui/app/session/page.tsx`

Changes implemented:
1. ✅ Import `useAvatarSpeech` hook
2. ✅ Connect avatar on session start (auto-connect when sessionId exists)
3. ✅ When `aiResponse` received from `/audio/chunk`:
   - If avatar connected: call `speakWithAvatar(aiResponse, emotion)`
   - If not connected (fallback): play `audioBase64` with static image
4. ✅ Display streaming avatar video via WebRTC
5. ✅ Cleanup on unmount (disconnect avatar)
6. ✅ Connection status indicator (spinner while connecting)
7. ✅ Error fallback indicator

**Deployment (2025-12-19):**
- UI deployed to: https://app-pulse-training-ui-prod.azurewebsites.net
- Startup command set: `node server.js`

---

### Phase 4: Audio Pipeline Enhancement (Optional) ❌ NOT STARTED

**Effort:** Small | **Risk:** Medium | **Dependencies:** Phase 3

#### 4.1 Optimize Response Contract

When avatar is active, backend can optionally skip TTS generation since avatar handles audio. Add to `/audio/chunk` response:

```json
{
  "aiResponse": "...",
  "avatarSsml": "<speak>...</speak>",
  "avatarEmotion": "friendly",
  "audioBase64": "..."  // Still included as fallback
}
```

---

### Phase 5: Testing & Validation ❌ NOT STARTED

**Effort:** Medium | **Risk:** Low | **Dependencies:** Phase 3

#### 5.1 Unit Tests

- `test_avatar_token.py` - Token endpoint returns valid response
- Verify CORS headers present
- Test disabled state returns 503

#### 5.2 Integration Tests

- Deploy to Azure
- Verify WebRTC connection establishes
- Test all 4 personas with avatar
- Verify fallback works when avatar service unavailable
- Test token refresh during long session

#### 5.3 Demo Validation Checklist

- [ ] 30-minute continuous conversation without interruption
- [ ] All 4 personas display correct avatar character/voice
- [ ] Lip sync matches speech
- [ ] No rate limiting (capacity at 50K+ TPM)
- [ ] Graceful recovery from network blips

---

## Dependency Graph

```
Phase 1 (Infrastructure)
    │
    ├─ 1.1 Speech key output
    ├─ 1.2 Function App env var
    │
    v
Phase 2 (Backend)
    │
    ├─ 2.1 Avatar token endpoint
    ├─ 2.2 UI proxy route
    │
    v
Phase 3 (UI - Core Feature)
    │
    ├─ 3.1 Install Speech SDK
    ├─ 3.2 Create useAvatarSpeech hook
    ├─ 3.3 Update session page
    │
    v
Phase 4 (Enhancement) ──────────────────┐
    │                                    │
    └─ 4.1 Optimize response contract    │
                                         │
Phase 5 (Testing) ◄──────────────────────┘
    │
    ├─ 5.1 Unit tests
    ├─ 5.2 Integration tests
    └─ 5.3 Demo validation
```

---

## Files to Create/Modify

### New Files

| File | Purpose |
|------|---------|
| `orchestrator/avatar_token/__init__.py` | Token endpoint handler |
| `orchestrator/avatar_token/function.json` | Function binding config |
| `ui/app/api/orchestrator/avatar/token/route.ts` | UI proxy route |
| `ui/hooks/useAvatarSpeech.ts` | React hook for avatar |
| `orchestrator/tests/test_avatar_token.py` | Unit tests |

### Modified Files

| File | Change |
|------|--------|
| `modules/speech/outputs.tf` | Add `speech_key` output ✅ **DONE** |
| `modules/app/variables.tf` | Add `speech_key` variable ✅ **DONE** |
| `modules/app/main.tf` | Add `AZURE_SPEECH_KEY` to app_settings ✅ **DONE** |
| `main.tf` | Pass speech key to app module ✅ **DONE** |
| `ui/package.json` | Add Speech SDK dependency |
| `ui/app/session/page.tsx` | Integrate avatar hook |

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| WebRTC connection failures | Medium | High | Fallback to static image + TTS audio |
| Token expiration mid-session | Medium | Medium | Proactive refresh at 8 minutes |
| Browser compatibility | Medium | Medium | Test Chrome, Safari, Firefox; document requirements |
| Network latency | Low | High | Use regional Azure endpoints |
| Avatar character unavailable | Low | Low | Default to "lisa" character |

---

## Pre-Implementation Checklist

Before starting implementation:

- [x] Terraform apply with increased capacity (50K/20K/4K TPM) ✅ **DONE 2025-12-19**
- [ ] Verify persona tests pass without rate limiting
- [x] Confirm Azure Speech Avatar is available in East US 2 region ✅ **DONE** (deployed as `speech-pulse-training-prod`)
- [ ] Review Speech SDK documentation for latest API

**Note:** Audio realtime capacity limited to 4 due to Azure quota (limit: 6). Request quota increase if needed.

---

## Post-Implementation Checklist

After implementation complete:

- [ ] All unit tests passing
- [ ] Integration tests passing
- [ ] 30-minute demo tested end-to-end
- [ ] Fallback path validated
- [ ] Documentation updated
- [ ] Consider setting `openai_public_network_access_enabled = false` after testing
