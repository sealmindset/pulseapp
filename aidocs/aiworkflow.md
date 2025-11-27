# PULSE Agentic AI: Agents, Prompts, Workflows, and Triggers

This document describes the Agentic AI composition used by the PULSE Behavioral Certification Platform, where the definitions live, how each workflow runs end‑to‑end, and when/where those flows are triggered in the app.

## Components and File Locations
- Orchestrator and agents (prompts/specs)
  - aidocs/trainer_prompts.md
    - Agentic AI Orchestrator (Manager)
    - Behavioral Compliance Evaluator (BCE)
    - Methodology & Content Fidelity Checker (MCF)
    - Conversion & Psychological Outcome Assessor (CPO)
- Next.js UI/UX (App Router)
  - ui/app/page.tsx (Pre‑Session)
  - ui/app/session/page.tsx (Session)
  - ui/app/feedback/page.tsx (Feedback)
  - ui/components/SessionContext.tsx (session state: persona, filters, sessionId, avatarUrl)
- Next.js API proxies (XHR only)
  - ui/app/api/orchestrator/session/start/route.ts → POST /session/start
  - ui/app/api/orchestrator/audio/chunk/route.ts → POST /audio/chunk
  - ui/app/api/orchestrator/session/complete/route.ts → POST /session/complete
  - ui/app/api/orchestrator/feedback/[sessionId]/route.ts → GET /feedback/{sessionId}
  - Admin (dev‑mode):
    - ui/app/api/orchestrator/admin/agents/route.ts
    - ui/app/api/orchestrator/admin/prompts/route.ts
    - ui/app/api/orchestrator/admin/prompts/[id]/route.ts
    - ui/app/api/orchestrator/admin/prompts/[id]/versions/route.ts
    - ui/app/api/orchestrator/admin/prompts/[id]/versions/[version]/route.ts
- Orchestrator (Azure Functions, Python) — Admin endpoints implemented in this repo
  - orchestrator/admin_agents/*  (GET/PUT /admin/agents)
  - orchestrator/admin_prompts/* (GET/POST /admin/prompts)
  - orchestrator/admin_prompts_by_id/* (GET/PUT/DELETE /admin/prompts/{id})
  - orchestrator/admin_prompt_versions/* (GET /admin/prompts/{id}/versions)
  - orchestrator/admin_prompt_version_item/* (GET /admin/prompts/{id}/versions/{version})
  - orchestrator/shared_code/blob.py (Azure Blob helpers, versioning)
- Orchestrator — Training/evaluation endpoints (expected)
  - /session/start, /audio/chunk, /session/complete, /feedback/{sessionId}
  - Note: These training/evaluation endpoints are referenced by the UI proxies but their server implementations are not included in this repo. Deploy them to the Function App alongside the admin endpoints.

## Diagrams
- [Pre-Session Start](./seq_pre_session_start.md)
- [Session Realtime Audio & Avatar](./seq_session_realtime_audio.md)
- [Complete Session](./seq_complete_session.md)
- [Feedback & Scoring](./seq_feedback_scoring.md)
- [Admin Prompt Editor (Dev Mode)](./seq_admin_prompt_editor.md)

## Agents and Prompts (from aidocs/trainer_prompts.md)
- Agentic AI Orchestrator (Manager)
  - Role: Distributes transcript to sub‑agents, aggregates scores, computes weighted final score, and determines pass/fail at ≥ 85% (and conversion confirmation).
  - Weights: BCE 40%, MCF 35%, CPO 25%.
  - Input: Turn‑by‑turn transcript + persona metadata.
  - Output: Consolidated JSON scorecard (see trainer_prompts.md for full schema).
- Behavioral Compliance Evaluator (BCE)
  - Focus: Platinum Rule adaptation, empathy/trust, CECAP/LERA emotional application.
  - Output: Score + brief summary.
- Methodology & Content Fidelity Checker (MCF)
  - Focus: Structural adherence to PULSE Steps 1–4, mini‑talks, accessory integration, closing foundation.
  - Output: Score + fidelity summary.
- Conversion & Psychological Outcome Assessor (CPO)
  - Focus: Urgency/FOMO, closing framework, financing pivots, ownership language, conversion outcome.
  - Output: Score + psychological tool usage + mandated conversion confirmation.

## Application Workflows and Triggers

### 1) Pre‑Session (Start Session)
- Trigger: User clicks “Start Session” on ui/app/page.tsx
- Flow:
  1. UI validates persona/prerequisite checkbox, then POSTs to ui/app/api/orchestrator/session/start/route.ts.
  2. Proxy forwards to Function App /session/start (FUNCTION_APP_BASE_URL), CORS open.
  3. Orchestrator returns { sessionId, avatarUrl? }.
  4. UI stores sessionId (+ avatarUrl if provided) in SessionContext and navigates to /session.
- Files involved:
  - UI page: ui/app/page.tsx
  - Proxy: ui/app/api/orchestrator/session/start/route.ts
  - Orchestrator: /session/start (server implementation expected)

### 2) Session (Realtime audio and avatar)
- Triggers:
  - “Start Mic” in ui/app/session/page.tsx starts MediaRecorder with 1s chunking.
  - Each ondataavailable event POSTs one chunk.
- Flow:
  1. UI posts FormData({ sessionId, chunk }) to ui/app/api/orchestrator/audio/chunk/route.ts.
  2. Proxy forwards to Function App /audio/chunk.
  3. Orchestrator performs ASR/analysis and returns any of:
     - JSON: { partialTranscript?, ttsUrl?, audioBase64? }
     - Raw audio/* payload
  4. UI appends partial transcript and plays returned audio (by URL or base64 or raw blob).
  5. Avatar: if avatarUrl given by start, UI renders it in the video area.
- Files involved:
  - UI page: ui/app/session/page.tsx
  - Proxy: ui/app/api/orchestrator/audio/chunk/route.ts
  - Orchestrator: /audio/chunk (server implementation expected)

### 3) Complete Session
- Trigger: User clicks “Complete Session” on ui/app/session/page.tsx
- Flow:
  1. UI POSTs { sessionId } to ui/app/api/orchestrator/session/complete/route.ts.
  2. Proxy forwards to Function App /session/complete.
  3. UI navigates to /feedback (regardless of response success in current implementation).
- Files involved:
  - UI page: ui/app/session/page.tsx
  - Proxy: ui/app/api/orchestrator/session/complete/route.ts
  - Orchestrator: /session/complete (server implementation expected)

### 4) Feedback and Scoring
- Trigger: Feedback page mount (ui/app/feedback/page.tsx) with a valid sessionId in SessionContext.
- Flow:
  1. UI GETs ui/app/api/orchestrator/feedback/[sessionId]/route.ts → Function App /feedback/{sessionId}.
  2. UI parses flexible response shape and renders:
     - Overall score (accepts 0–1 or 0–100 as `overallScore` | `score` | `mastery`).
     - Rubric array (name/label, score, passed, notes).
     - Artifacts: audioUrl | audioBase64, transcript (array or string).
- Files involved:
  - UI page: ui/app/feedback/page.tsx
  - Proxy: ui/app/api/orchestrator/feedback/[sessionId]/route.ts
  - Orchestrator: /feedback/{sessionId} (server implementation expected)

## Admin Prompt Editing (Dev Mode, No Auth)
- Visibility gate (UI):
  - NEXT_PUBLIC_ENABLE_ADMIN=true AND NEXT_PUBLIC_ENV_NAME != "prod"
- Visibility gate (Function App writes):
  - ADMIN_EDIT_ENABLED=true required for POST/PUT/DELETE (dev only)
- UI location: ui/app/admin/page.tsx
  - Tabs:
    - Prompts: list/search, view, create, edit, delete, view versions
    - Agents: table editor with add/remove/save
- Next.js proxies (open CORS):
  - /api/orchestrator/admin/agents (GET/PUT)
  - /api/orchestrator/admin/prompts (GET/POST)
  - /api/orchestrator/admin/prompts/[id] (GET/PUT/DELETE)
  - /api/orchestrator/admin/prompts/[id]/versions (GET)
  - /api/orchestrator/admin/prompts/[id]/versions/[version] (GET)
- Orchestrator implementation (in this repo):
  - Endpoints above exist under orchestrator/* with Azure Blob persistence and content versioning.
  - Container: prompts (auto‑created). Files:
    - agents.json
    - prompts/{id}.json
    - prompts/{id}/versions/{n}.json
- Notes:
  - Client logs avoid IDs; server logs can include ids for correlation.
  - For production, disable ADMIN_EDIT_ENABLED or add AAD/RBAC and stricter CORS.

## Data Contracts (UI Expectations)
- Start Session response: { sessionId: string, avatarUrl?: string }
- Audio Chunk response (one of):
  - JSON: { partialTranscript?: string, ttsUrl?: string, audioBase64?: string }
  - raw audio/*
- Complete Session: 200/204 acknowledged (body ignored by UI)
- Feedback: flexible JSON with keys like:
  - overallScore | score | mastery (number 0–1 or 0–100)
  - rubric: [{ name|label, score?, passed?, notes? }]
  - artifacts: { audioUrl?, audioBase64?, transcript?: string|string[] }

## Security and Networking
- Azure OpenAI and Storage are private‑only with Private Endpoints; UI cannot access them directly.
- Function App is VNet‑integrated; UI talks to it via Next.js proxies (XHR only). CORS open on server responses.
- Certification pass threshold enforced by orchestrator logic is ≥ 0.85.

## Known Gaps / Next Steps
- Training orchestrator endpoints (/session/*, /audio/*, /feedback/*) are referenced but their server implementation is not included in this repo. They should:
  - Perform ASR/analysis and sub‑agent orchestration per aidocs/trainer_prompts.md.
  - Persist session artifacts and scoring outputs for retrieval by /feedback/{sessionId}.
- Add tests for Admin flows and end‑to‑end session/feedback.
