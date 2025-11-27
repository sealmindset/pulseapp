
### Orchestrator (Admin Endpoints)
- Implemented Azure Functions (Python) endpoints under `/orchestrator`:
  - `GET/PUT   /admin/agents`
  - `GET/POST  /admin/prompts`
  - `GET/PUT/DELETE /admin/prompts/{id}`
  - `GET      /admin/prompts/{id}/versions`
  - `GET      /admin/prompts/{id}/versions/{version}`
- Storage persistence: Azure Blob via connection string (`BLOB_CONN_STRING`/`AZURE_STORAGE_CONNECTION_STRING`/`AzureWebJobsStorage`), container `prompts` (auto-created).
- Dev gating: write operations require `ADMIN_EDIT_ENABLED=true`.
- CORS: `Access-Control-Allow-Origin: *` for XHR compatibility with the UI proxies.
### Admin (Dev Mode Prompt Editor)
- Added `/admin` UI (dev-only, no auth) gated by `NEXT_PUBLIC_ENABLE_ADMIN=true` and `NEXT_PUBLIC_ENV_NAME!=prod`.
- Implemented Next.js API proxy routes:
  - `GET/PUT   /api/orchestrator/admin/agents`
  - `GET/POST  /api/orchestrator/admin/prompts`
  - `GET/PUT/DELETE /api/orchestrator/admin/prompts/{id}`
  - `GET      /api/orchestrator/admin/prompts/{id}/versions`
  - `GET      /api/orchestrator/admin/prompts/{id}/versions/{version}`
- UI components:
  - `PromptsManager` (list/search, view/edit/create/delete prompts, view versions)
  - `AgentsManager` (table edit with add/remove/save)
- Orchestrator dependency: requires Function App endpoints under `/admin/*` and storage (private container) with versioning; enable writes via `ADMIN_EDIT_ENABLED=true` in dev; disable or require auth in prod.
# Changelog
### UI/UX (Next.js Skeleton)
- Created Next.js app scaffold under `/ui` (App Router, TypeScript, Tailwind):
  - Config: `package.json`, `next.config.mjs`, `tsconfig.json`, `postcss.config.js`, `tailwind.config.ts`, `next-env.d.ts`, `.env.example`.
  - App Router: `app/layout.tsx`, `app/globals.css`, `app/page.tsx`, `app/session/page.tsx`, `app/feedback/page.tsx`.
  - Components: `components/PersonaSelector.tsx`, `components/ScenarioFilters.tsx`, `components/PULSEProgressBar.tsx`.
  - API route proxy (XHR): `app/api/orchestrator/audio/chunk/route.ts`.
- Terraform default Web App runtime set to `NODE|18-lts` for Next.js hosting.
- Notes:
  - Run locally: `npm install` then `npm run dev` in `/ui`.
  - Set `.env.local`: `FUNCTION_APP_BASE_URL`, `APPINSIGHTS_CONNECTION_STRING`, and optional `NEXT_PUBLIC_ENV_NAME`.
  - Lint/type errors clear after installing deps.


## 2025-11-20

### Added
- Network diagram generator script `PULSE_network_diagram.py` using `mingrammer/diagrams` with official Azure icons.
- Diagram models the Terraform architecture:
  - Resource Group, VNet, Subnets (App and Private Endpoints)
  - Private Endpoints for Azure OpenAI, Storage (Blob), and Web App
  - Azure OpenAI (Cognitive Account), Storage Account
  - App Service Plan, Web App (UI/API), Function App (Scenario Orchestrator)
  - Private DNS Zones (openai, blob, azurewebsites)
  - Log Analytics Workspace and Application Insights
  - Connectivity edges for Private Link paths, diagnostics to Log Analytics, and telemetry to App Insights

### Notes
- Default outputs: `PULSE-network-diagram.png` and `PULSE-network-diagram.svg` (generated on run).
- Optional draw.io export: see `--drawio` flag below for generating `<basename>.drawio` files that can be imported into draw.io / Lucidchart.
- Requires Graphviz binaries and Python packages (`diagrams`, `graphviz`).
- Does not modify infrastructure; visualization only, but now diagrams all core Terraform-managed resources and relationships for the platform.

### Updated
- Diagram script now renders both PNG and SVG outputs and has been expanded to represent all core Terraform resources (VNet, subnets, all Private Endpoints, Azure OpenAI account + deployments, Storage Account + containers, App Service Plan, Web App, Function App, Private DNS zones/links, diagnostics, Log Analytics, and Application Insights).
- Added CLI args:
  - `--tf-path` to point at the Terraform project (defaults to repo root when running from `docs/`).
  - `--output-basename` to control output filename.
  - `--direction` to switch layout direction.
- Added extended usage/help flags `--usage`/`--usuage` including requirements, expected Terraform files, and step-by-step examples.
- Added `--drawio` flag to emit a draw.io XML file (`<basename>.drawio`) that can be imported into Lucidchart or diagrams.net, skipping PNG/SVG rendering when used.

### Terraform (PULSE Visual & Verbal Platform)
- Added Azure OpenAI deployment `Persona-Visual-Asset` for persona-specific avatar and context image generation (e.g., `gpt-image-1`/`dall-e-3`). This model is intended to be invoked by the Function App orchestrator as part of `/session/start`, with the resulting avatar image persisted to Storage and returned to the UI as an `avatarUrl` (the Web App never calls Azure OpenAI directly).
- Enforced AzureRM v4 compatibility:
  - Removed unsupported `tags` from `azurerm_cognitive_deployment` resources (not supported in v4).
  - Replaced deprecated `metric {}` with `enabled_metric {}` in all diagnostic settings.
  - Removed deprecated `allow_blob_public_access` from `azurerm_storage_account` (use `public_network_access_enabled=false` + Private Endpoints).
- Strengthened security posture:
  - Azure OpenAI `public_network_access_enabled = false` and Private Endpoint + `privatelink.openai.azure.com` DNS zone.
  - Storage Account `public_network_access_enabled = false`; containers are private.
  - App Service and Function App integrated with VNet (Swift connection); optional Web App Private Endpoint toggle.
- Application settings:
  - Added `OPENAI_DEPLOYMENT_PERSONA_VISUAL_ASSET` app setting to surface the Persona-Visual-Asset deployment name for persona avatar/context image generation. In the current Terraform wiring this is applied to the Web App configuration; the architectural intent is for the Function App orchestrator to use this deployment when generating avatars and to expose only an `avatarUrl` back to the Web App.
  - `BEHAVIORAL_MASTERY_THRESHOLD` default 0.85 with validation (must be 0.85–1.0).

## 2025-11-21

### UI/UX (Session + Feedback)
- Implemented avatar rendering on Session page using `avatarUrl` from SessionContext with graceful placeholder fallback.
- Implemented real-time audio chunk upload via XHR (FormData) to orchestrator proxy and immediate playback of returned audio responses:
  - Supports JSON payloads with `ttsUrl` and/or `audioBase64` as well as raw `audio/*` responses.
  - Appends partial transcripts when provided as `partialTranscript`.
- Added "Complete Session" CTA posting to `/api/orchestrator/session/complete` then navigating to Feedback page.
- Implemented Feedback page client-side fetching via `/api/orchestrator/feedback/[sessionId]` with:
  - Loading and error states, flexible score parsing (`overallScore`/`score`/`mastery`).
  - Rubric rendering from `rubric[]` including name/score/passed/notes when present.
  - Artifacts section with audio (`audioUrl` or `audioBase64`) and transcript display (array or string).
  - No-session notice with link back to Pre-Session if `sessionId` context is not set.

### Notes
- Ensure `.env.local` defines `FUNCTION_APP_BASE_URL` (Function App base URL) for all orchestration proxy routes.
- Feedback retrieval requires `sessionId` retained in SessionContext; a hard page reload on the Feedback page without prior session context shows a gentle notice.

### Docs
- Added comprehensive `README.md` at repo root:
  - Project overview and purpose.
  - Prerequisites including Azure permissions and provider registrations.
  - Supported environments and example `*.tfvars`.
  - Terraform init/plan/apply steps and notes on private networking.
  - Next.js UI/UX setup and run (local dev and production build).
 - Added `aidocs/aiworkflow.md` documenting agents/prompts, file locations, workflows, and triggers.
 - Added Mermaid sequence diagrams under `aidocs/` for key workflows:
   - `seq_pre_session_start.md` — Pre-Session Start
   - `seq_session_realtime_audio.md` — Session Realtime Audio & Avatar
   - `seq_complete_session.md` — Complete Session orchestration (Manager + BCE/MCF/CPO)
   - `seq_feedback_scoring.md` — Feedback & Scoring retrieval
   - `seq_admin_prompt_editor.md` — Admin Prompt Editor (Dev Mode)
 - Added `.gitignore` covering Node.js, Terraform, Python, editor files, and environment files (excludes `.env.example`).
 - Added `docs/capabilities.md` capturing Azure OpenAI audio/vocalization capabilities (real-time audio models, STT/TTS) and how they support the immersive PULSE behavioral certification use case.

### Terraform / CI
- Introduced Terraform modules under `modules/`:
  - `modules/openai` encapsulates Azure OpenAI cognitive account + all persona deployments.
  - `modules/app` encapsulates App Service Plan, Web App (UI/API) + VNet integration, and Function App (Scenario Orchestrator) + VNet integration.
- Refactored `main.tf` to consume `module.openai` and `module.app`:
  - All OpenAI references (endpoints, deployment names, diagnostics, private endpoints) now use module outputs.
  - Web App / Function App diagnostics and Web App Private Endpoint now target `module.app` outputs.
- Added Terraform `moved` blocks in `main.tf` to safely migrate existing state from root resources to module-based resources (OpenAI account/deployments, App Service Plan, Web App, Function App, and their VNet integrations) and avoid unintended recreation.
- Added GitHub Actions workflow `.github/workflows/ci-infra-ui.yml`:
  - Terraform job (root): `fmt`, `init`, `validate`, and `plan` for PRs (`TF_VAR_environment=staging`).
  - UI job (`ui/`): Node 18, `npm ci`, optional `lint`/`test`, and `build` for the Next.js app.

## 2025-11-26

### Terraform / Observability
- Tightened Azure Monitor diagnostic settings in `main.tf` to match observability spec:
  - `azurerm_monitor_diagnostic_setting.diag_openai` now enables both `Audit` and `RequestResponse` log categories for the Azure OpenAI cognitive account (where supported), streaming to Log Analytics.
  - `azurerm_monitor_diagnostic_setting.diag_functionapp` now emits both `FunctionAppLogs` and `AppServiceHTTPLogs` for the Scenario Orchestrator Function App, improving HTTP-level tracing in Log Analytics.
- Kept existing diagnostics for Storage (`StorageRead/Write/Delete`) and Web App (`AppServiceHTTPLogs`, `AppServiceConsoleLogs`) unchanged.

### Docs / Network Diagram
- Updated `docs/PULSE_network_diagram.py` to label diagnostic-setting edges with the concrete log categories now configured in Terraform:
  - `diag_openai (Audit, RequestResponse)` from Azure OpenAI to Log Analytics.
  - `diag_storage (StorageRead/Write/Delete)` from Storage to Log Analytics.
  - `diag_webapp (HTTPLogs, ConsoleLogs)` from Web App to Log Analytics.
  - `diag_functionapp (FunctionAppLogs, AppServiceHTTPLogs)` from Function App to Log Analytics.
- These labels keep the rendered PNG/SVG/draw.io diagrams in sync with the actual Terraform diagnostics configuration and make it easier to reason about which logs are flowing where during PULSE training sessions.

## 2025-11-27

### CI / UI
- Added minimal ESLint configuration file `ui/.eslintrc.json` extending `next/core-web-vitals` so that `next lint` runs non-interactively in both local and CI environments.
- This prevents the Next.js ESLint setup wizard from prompting in GitHub Actions when `npm run lint` is executed, unblocking the `UI Lint & Build` job in `.github/workflows/ci-infra-ui.yml`.
- No changes to the lint script itself (`"lint": "next lint"`); behavior is controlled via the new config file.
