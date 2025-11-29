
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
 - Further annotated the Function App node with its key HTTP routes (`/session/*`, `/audio/chunk`, `/trainer/pulse/step`, `/admin/*`) and expanded the Storage Account cluster to include `prompts` and `trainer-change-logs` containers so the diagram highlights the PULSE Trainer and evaluator surfaces without exposing application internals.

## 2025-11-27

### CI / UI
- Added minimal ESLint configuration file `ui/.eslintrc.json` extending `next/core-web-vitals` so that `next lint` runs non-interactively in both local and CI environments.
- This prevents the Next.js ESLint setup wizard from prompting in GitHub Actions when `npm run lint` is executed, unblocking the `UI Lint & Build` job in `.github/workflows/ci-infra-ui.yml`.
- No changes to the lint script itself (`"lint": "next lint"`); behavior is controlled via the new config file.

### PULSE Trainer (Phase A Scaffold)
- Added Azure Function HTTP endpoint `trainer_pulse_step` with route `POST /trainer/pulse/step` returning a stubbed PULSE Trainer Agent `OUTPUT` envelope for a single PULSE step, honoring the `adaptive_trainer.enabled` flag but not yet calling any LLM.
- Added Next.js API proxy route `app/api/orchestrator/trainer/pulse/step/route.ts` that forwards JSON bodies to the Function App via `FUNCTION_APP_BASE_URL`, mirroring existing `/session/*` and `/feedback/*` proxy patterns and keeping CORS open for XHR.
- Introduced a Training page `app/training/page.tsx` that exercises the trainer endpoint with a fixed Probe scenario, collects the learner’s verbal or free-text answer, and renders the stub diagnosis and next question for manual end-to-end testing before wiring in full LLM logic.
- Refined the `/training` UX into a two-column layout that mirrors the planned production flow: left side for scenario and trainer question/answer, right side for Probe rubric (success criteria and common errors), trainer feedback, and a stub mastery status panel, so the visual structure is stable before LLM-powered behavior is enabled.

### PULSE Trainer (Phase B LLM Wiring)
- Updated `orchestrator/trainer_pulse_step/__init__.py` to call Azure OpenAI when `adaptive_trainer.enabled` is true, using `OPENAI_ENDPOINT`, `OPENAI_API_VERSION`, `AZURE_OPENAI_API_KEY`, and either `OPENAI_DEPLOYMENT_PERSONA_HIGH_REASONING` or `OPENAI_DEPLOYMENT_PERSONA_CORE_CHAT` to create a chat completion with a PULSE Trainer system prompt and `CONFIG`/`SESSION` JSON payload, requesting a strict JSON `OUTPUT` object matching the trainer schema.
- Preserved static evaluation behavior when adaptive training is disabled and added a resilient fallback stub path that returns a deterministic `OUTPUT` envelope if the LLM call fails for any reason, so the `/training` page remains usable even without Azure OpenAI configuration.
- Added `requests` to `orchestrator/requirements.txt` as the minimal dependency for performing Azure OpenAI REST calls from the Function App, without introducing a broader SDK dependency.

### PULSE Trainer (Phase C Self-Annealing Logging)
- Extended `orchestrator/trainer_pulse_step/__init__.py` with a `_maybe_log_trainer_change` helper that inspects the trainer’s JSON `OUTPUT` and, when `trainer_change_log.emit == true`, writes a structured log document to the prompts blob container under the `trainer-change-logs/` prefix, keyed by date, PULSE step, scenario id, and session id.
- Logged payloads include timestamp, basic session identifiers, the runtime CONFIG, and the `trainer_change_log` object so that recurring patterns and proposed rubric/prompt/scenario changes can be reviewed offline and fed back into trainer SOPs, without impacting live request latency or requiring database schema changes.
- Any failures in this logging path are caught and logged via `logging.exception` but do not affect the learner experience, keeping the self-annealing signal path best-effort and non-disruptive.

### PULSE Trainer (Phase D Rollout & Gating)
- Gated the Training nav and `/training` page behind `NEXT_PUBLIC_ENABLE_TRAINING` and `NEXT_PUBLIC_ENV_NAME!=prod` so that PULSE Training is only visible and usable in explicitly enabled non-production environments.
- Added a `PULSE_TRAINER_ENABLED` Function App setting check in `trainer_pulse_step` so the backend must be explicitly turned on before calling Azure OpenAI; when disabled, the endpoint returns a static-evaluation `OUTPUT` indicating that the trainer is off for this environment.
- Documented the PULSE Trainer dev-preview path, gating env vars, and Azure OpenAI configuration requirements in `README.md` so operators can safely enable or keep the trainer dark per environment.

### PULSE Refactor (Phase 2 – Apply Across Code, UI, Docs, Prompts)
- Updated remaining documentation prompts (`docs/aistudio.md`, `docs/explained.md`, `aidocs/simulation.md`, `aidocs/trainer_prompts.md`) so that the active sales methodology is consistently described as **PULSE Selling** rather than “Selling by Numbers”, avoiding restatement of proprietary legacy content.
- Clarified the canonical five-step PULSE Selling framework (Probe, Understand, Link, Simplify, Earn) in docs where the methodology was previously framed as a six-step process.
- Adjusted the session progress bar component naming to `PulseProgressBar` in the UI to better reflect the current methodology while keeping visual behavior unchanged.

### PULSE Refactor (Phase 3 – Sanity Check & Tests)
- Added orchestrator tests under `orchestrator/tests/test_trainer_pulse_step.py` to cover `trainer_pulse_step` behavior, including:
  - CORS + preflight handling (OPTIONS) and method/JSON validation errors.
  - Environment gating via `PULSE_TRAINER_ENABLED` (static-evaluation response when disabled).
  - Static evaluation path when `adaptive_trainer.enabled` is false in the CONFIG.
  - Resilient fallback behavior when the Azure OpenAI trainer call fails, ensuring a deterministic `OUTPUT` envelope is still returned.
  - Self-annealing logging helper `_maybe_log_trainer_change`, verifying that no-op occurs when `emit=false` and that an appropriate blob path/payload is written when `emit=true`.
- Introduced lightweight Jest + ts-jest configuration for the UI (`ui/jest.config.cjs`) and focused component tests in `ui/__tests__/` to validate:
  - `/training` gating behavior based on `NEXT_PUBLIC_ENABLE_TRAINING` and `NEXT_PUBLIC_ENV_NAME` using server-side rendering of `TrainingPage`.
  - `PulseProgressBar` rendering of the five PULSE Selling steps (Probe, Understand, Link, Simplify, Earn) on the Session page.

### PULSE Evaluator Prompt (0–3 PULSE Scoring)
- Promoted `docs/pulseagent.md` as the canonical system prompt for the evaluator/coach agent, defining a PULSE Selling-based 0–3 scoring scale per step and the exact JSON response contract expected from the evaluator.
- Added implementation notes to `docs/pulseagent.md` documenting how to seed this prompt via the Admin Prompts UI, including `id`/`agentId` (`pulse-evaluator-v1`), `title` (`PULSE Evaluator (0–3 PULSE steps)`), and `type` (`system`), so operators can reliably create and update the prompt in each environment.
- Introduced `aidocs/pulse_evaluator_prompt_seed.json` as a lightweight, copy-paste seed file that captures the evaluator prompt metadata and points back to `docs/pulseagent.md` for the full markdown body, aligning with the existing blob-backed prompts/versions infrastructure.
- Updated `aidocs/aiworkflow.md` to reference the new PULSE Evaluator agent and its prompt locations, clarifying how it will be used by future `/feedback/{sessionId}` implementations alongside the existing BCE/MCF/CPO agent design.
- Left the BCE/MCF/CPO orchestration schema (percentage scores and ≥0.85 pass threshold) unchanged for now, treating the PULSE Evaluator as a parallel, simpler scoring path that uses the new PULSE 0–3 JSON schema for post-session coaching.

### Docs / Capabilities
- Expanded `docs/capabilities.md` beyond audio/vocalization to describe how the platform’s Azure OpenAI and networking foundation now supports:
  - The PULSE Trainer Agent dev-preview flow (`/training` + `POST /trainer/pulse/step`) for step-focused PULSE coaching with adaptive follow-ups, mastery estimates, and optional self-annealing `trainer_change_log` signals.
  - The PULSE Evaluator/Coach capability built around a 0–3 PULSE step scoring schema and structured JSON feedback, seeded via the `pulse-evaluator-v1` system prompt defined in `docs/pulseagent.md` and managed through the Admin Prompts UI.
  - Dev-mode Admin Prompt editing and versioned prompt storage on private Azure Blob, keeping RESTRICTED IP content server-side while enabling iterative improvement of training prompts and rubrics.

## 2025-11-28

### Phase 0 – PULSE Training Business Readiness Assessment
- Finalized `aidocs/phase0_sbn_training_assessment.md` as the canonical Phase 0 business readiness assessment for PULSE training, including a persona/outcome test matrix, flow checks, admin UX checklist, and infra/performance sanity criteria.
- Added a 2025-11-28 preliminary assessment subsection to record a desk-based readiness review of this repo’s current contents (Terraform, orchestrator stubs, UI, and docs) without running the full simulation engine.
- Determined that, based on this repo alone, the platform is **not yet ready** for a full PULSE training pilot because:
  - Training orchestrator endpoints (`/session/start`, `/audio/chunk`, `/session/complete`, `/feedback/{sessionId}`) are referenced but their server implementations are not included here and must be supplied/deployed alongside the admin endpoints.
  - BCE/MCF/CPO scoring and the full simulation engine exist only as documented prompt designs (no implemented pipeline or scorecard envelope in this codebase).
  - The new PULSE 0–3 Evaluator/Coach prompt is defined and seeded but not yet wired into a live feedback pipeline.
- Captured these gaps and the expected remediation steps (implement orchestrator endpoints, BCE/MCF/CPO pipeline, and evaluator integration, followed by targeted matrix runs) so future teams can re-run Phase 0 against a deployed environment and move confidently into hardened pilot phases.

### Training/Evaluator Orchestrator (Phase A–C)
- Phase A: Implemented core training/evaluator orchestrator endpoints in the Function App to back the existing UI proxies without introducing fake scoring data:
  - `POST /session/start` creates a new session, persists a lightweight `sessions/{sessionId}/session.json` document to the prompts container (session metadata only), and returns `{ sessionId, avatarUrl: null }` with open CORS.
  - `POST /session/complete` marks the session as completed in the same blob document and returns `204 No Content`, matching the UI’s expectations.
  - `POST /audio/chunk` accepts audio requests and responds with an honest stub text when `TRAINING_ORCHESTRATOR_ENABLED=true`, and a clear 503 error when disabled; audio processing (STT/TTS) is intentionally deferred to later phases to avoid mock evaluation.
  - `GET /feedback/{sessionId}` now returns a minimal feedback envelope containing `session` metadata and `artifacts.transcript` (when present), so the Feedback page can render artifacts even before scoring is wired.
- Phase B: Introduced a BCE/MCF/CPO scorecard contract and consumption path without faking scores:
  - Defined a scorecard blob contract at `sessions/{sessionId}/scorecard.json` with `overall`, `bce`, `mcf`, and `cpo` objects, each carrying a numeric `score` and optional `passed`/`summary` fields.
  - Extended `feedback_session` to read this scorecard and map it into the UI’s flexible contract as `overallScore` and a `rubric` array (Behavioral Mastery/BCE, Methodology Fidelity/MCF, Conversion Outcome/CPO), while also returning the raw `scorecard` for downstream consumers.
  - Left scorecard **generation** out of this repo per Phase 0 findings; external orchestrators or future Functions are responsible for writing `scorecard.json`, keeping this implementation honest and side-effect free when scores are not yet available.
- Phase C: Integrated the PULSE 0–3 evaluator into the feedback flow behind strict env and config gating:
  - Added `PULSE_EVALUATOR_ENABLED` and `PULSE_EVALUATOR_PROMPT_ID` gating so the evaluator only runs when explicitly enabled and configured.
  - Implemented prompt loading from blob (`prompts/{id}.json`, default `pulse-evaluator-v1`) using the Admin-managed system prompt defined in `docs/pulseagent.md`.
  - Implemented an Azure OpenAI chat completion call that sends the full session transcript and persona as JSON to the evaluator prompt and expects a strict JSON object (framework/scores/overall_summary) per the PULSE 0–3 schema.
  - Wired `/feedback/{sessionId}` to attach the evaluator result under `pulseEvaluator` when enabled and a non-empty transcript is available; failures or missing config are logged server-side and simply omit the evaluator field, never returning fabricated feedback.

### Analytics PostgreSQL (Longitudinal Store & Readiness DB)
- Added a dedicated `analytics_postgres` Terraform module under `modules/analytics_postgres` that provisions an Azure Database for PostgreSQL Flexible Server as the **system of record** for longitudinal training analytics and readiness snapshots:
  - Creates a delegated subnet `PULSE-analytics-pg-subnet` in the existing VNet using `Microsoft.DBforPostgreSQL/flexibleServers` delegation.
  - Creates a private DNS zone `privatelink.postgres.database.azure.com` and links it to the PULSE VNet so the Web App and Function App can resolve the Postgres FQDN privately.
  - Provisions a private-only PostgreSQL Flexible Server (`pg-<project>-analytics-<env>`) with configurable version, SKU, storage, and backup retention, plus a dedicated `pulse_analytics` database.
- Wired the new module into `main.tf` with explicit sizing and credential variables:
  - `analytics_pg_subnet_prefix`, `analytics_pg_version`, `analytics_pg_sku_name`, `analytics_pg_storage_mb`, `analytics_pg_backup_retention_days`.
  - `analytics_pg_admin_username`, `analytics_pg_admin_password` (sensitive, supplied via `*.tfvars` or secret store only).
- Exposed non-sensitive connection details via Terraform outputs for operators and tooling:
  - `analytics_pg_fqdn` and `analytics_pg_database_name`.
- Plumbed analytics connection details into the Web App and Function App as environment variables so backend services can build a `PULSE_ANALYTICS_DATABASE_URL` at runtime and target the analytics database for:
  - Longitudinal Analytics Store tables (e.g., `session_events`, `user_skill_agg`).
  - Readiness snapshot tables (e.g., `user_readiness`).
  - `PULSE_ANALYTICS_DB_HOST`, `PULSE_ANALYTICS_DB_PORT`, `PULSE_ANALYTICS_DB_NAME`, `PULSE_ANALYTICS_DB_USER`, `PULSE_ANALYTICS_DB_PASSWORD`.
- Left schema creation and migrations to the application layer so that analytics tables can evolve via normal migration tooling while Terraform owns only the server, subnet, DNS, and base database.

### Longitudinal Analytics Store & Readiness Score (Phase E/F Implementation)
- Added canonical analytics schema under `setup/schema.sql` for the dedicated `pulse_analytics` PostgreSQL database:
  - Schemas: `analytics` (storage) and `api` (PostgREST-facing views).
  - Tables (all with `id uuid primary key default gen_random_uuid()` and `api_id bigserial unique` as per PostgREST/UUID conventions):
    - `analytics.session_events` — per-user / per-session / per-skill events with `user_id`, `session_id`, `occurred_at`, `scenario_id`, `pulse_step`, `skill_tag`, `score` (0–100), `raw_metrics` (JSONB), and `notes`.
    - `analytics.user_skill_agg` — rolling aggregates by `user_id` + `skill_tag` + `window` (e.g., `30d`) with `avg_score`, `sample_size`, `last_updated`, and a unique constraint on `(user_id, skill_tag, window)` to support upserts.
    - `analytics.user_readiness` — readiness snapshots over time with `user_id`, `snapshot_at`, `readiness_overall`, component fields (`readiness_technical`, `readiness_communication`, `readiness_structure`, `readiness_behavioral`), and `meta` (JSONB for formula/windows).
  - Views in `api.*` expose `api_id` as external `id` and include `uuid` as a separate column, keeping internal joins on UUIDs while supporting numeric IDs at the PostgREST HTTP boundary.
- Documented schema application and migration strategy in `setup/README.md`:
  - For a fresh analytics DB, run `psql` against `pulse_analytics` with `setup/schema.sql` using the analytics env vars provisioned by Terraform.
  - For future changes, use incremental SQL under `setup/migrations/` and keep `schema.sql` in sync with the current desired state, taking backups before any breaking change.
- Implemented a lightweight analytics/Postgres client and event helper in the orchestrator:
  - `orchestrator/shared_code/analytics_db.py` builds a DSN from `PULSE_ANALYTICS_DB_HOST/NAME/USER/PASSWORD/PORT` and exposes a `get_connection()` context manager using `psycopg[binary]` for short-lived read/write operations.
  - `orchestrator/shared_code/analytics_events.py` adds `record_session_scorecard_event(session_id, session_doc, scorecard)` which, when `PULSE_ANALYTICS_ENABLED=true`, inserts a single `session_end`/`overall` row into `analytics.session_events` with the full scorecard stored in `raw_metrics` for later longitudinal analysis.
  - `feedback_session` now calls `record_session_scorecard_event` after successfully loading and mapping a non-empty BCE/MCF/CPO scorecard, remaining a no-op when analytics are disabled or misconfigured.
- Implemented a readiness aggregation service to compute and persist readiness snapshots:
  - `orchestrator/shared_code/readiness_service.py` provides:
    - `compute_and_store_user_readiness(user_id)` which, when `PULSE_READINESS_ENABLED=true`,
      - Reads `analytics.session_events` for the user over the last 30 days,
      - Aggregates by `skill_tag` into `analytics.user_skill_agg` (window `30d`) via upsert,
      - Maps skill tags to readiness components (`technical_depth`, `communication`, `structure`, `behavioral_examples`),
      - Computes component averages and an overall readiness score using configurable weights,
      - Inserts a snapshot into `analytics.user_readiness` with a `meta` JSON documenting formula version, window, and weights.
    - `compute_and_store_user_readiness_for_session(session_doc)` which extracts a `user_id` from the session (valid UUID only) and delegates to the above, acting as a safe, id-aware entrypoint for orchestrator endpoints.
  - `feedback_session` invokes `compute_and_store_user_readiness_for_session(session_doc)` after recording the scorecard event, so each scored session can produce a new readiness snapshot for that user when flags and IDs are present.
- Added dedicated readiness/query endpoints in the orchestrator and wired them through the UI:
  - `orchestrator/readiness` (`GET /readiness/{userId}`): returns the latest and recent readiness snapshots for a user (`latest` + `history`), reading from `analytics.user_readiness` and enforcing the same `TRAINING_ORCHESTRATOR_ENABLED` gating used elsewhere.
  - `orchestrator/readiness_skills` (`GET /readiness/{userId}/skills`): returns skill-level aggregates from `analytics.user_skill_agg` for the `30d` window, suitable for trend/breakdown views.
  - Next.js proxy routes:
    - `ui/app/api/orchestrator/readiness/[userId]/route.ts` → proxies to `/readiness/{userId}`.
    - `ui/app/api/orchestrator/readiness/[userId]/skills/route.ts` → proxies to `/readiness/{userId}/skills`.
- Introduced a minimal Readiness UI surface on the Feedback page:
  - `ui/components/useReadiness.ts` exposes `useReadiness(userId)` which fetches `/api/orchestrator/readiness/{userId}` and returns `{ loading, error, data }` with a strongly typed readiness history.
  - `ui/components/ReadinessCard.tsx` renders an experimental “Readiness (Pilot)” card showing the latest overall readiness score (0–100) with a coarse band label (“Strong” / “Emerging” / “Early”) and per-component scores (Technical, Communication, Structure, Behavioral).
  - `ui/app/feedback/page.tsx` optionally includes `<ReadinessCard userId={readinessUserId} />` in the right-hand column when `NEXT_PUBLIC_PULSE_READINESS_USER_ID` is set, keeping readiness display opt-in and scoped to specific test users during pilot.
- Added orchestrator tests for analytics and readiness paths in `orchestrator/tests/test_analytics_readiness.py`:
  - Verify that analytics and readiness helpers respect `PULSE_ANALYTICS_ENABLED` and `PULSE_READINESS_ENABLED` flags and do not open DB connections when disabled.
  - Confirm that `record_session_scorecard_event` produces the expected INSERT payload into `analytics.session_events` when enabled.
  - Validate that `compute_and_store_user_readiness` computes weighted readiness correctly from mocked aggregates and attempts an INSERT into `analytics.user_readiness`.
  - Exercise the new `/readiness/{userId}` and `/readiness/{userId}/skills` endpoints with mocked connections, asserting that they return the expected JSON envelopes.
  - Note: running these tests locally requires installing `azure-functions` and `psycopg[binary]` into a virtualenv (use `pip install -r orchestrator/requirements.txt`) before invoking `python -m unittest discover orchestrator/tests`.

## 2025-11-28

### Readiness Identity & user_id Threading
- Tightened readiness behavior to rely on a real, stable `user_id` rather than implicit or synthetic identifiers:
  - `orchestrator/session_start` now extracts an optional `userId`/`user_id` field from the request body or an `X-PULSE-User-Id` header, validates that it is a UUID, and persists it into `sessions/{sessionId}/session.json` as `user_id` when valid.
  - Readiness aggregation (`compute_and_store_user_readiness_for_session`) continues to operate only when a valid UUID `user_id` is present on the session document, ensuring readiness snapshots are always keyed to a stable learner identity.
- Added a minimal pilot identity mapping in the Pre-Session UI so longitudinal analytics and readiness can be exercised without a full auth stack:
  - `ui/app/page.tsx` now reads an optional `NEXT_PUBLIC_PULSE_USER_ID` (or falls back to `NEXT_PUBLIC_PULSE_READINESS_USER_ID`) and, when present, passes it as `userId` in the `/api/orchestrator/session/start` payload.
  - This value is treated as a UUID and becomes the canonical `user_id` used by analytics/readiness for that learner during pilots.
- Extended orchestrator tests to cover the new identity behavior:
  - `orchestrator/tests/test_session_endpoints.py` now verifies that when `session_start` receives a `userId` in the request body, it persists the corresponding `user_id` into the blob-backed session document via `write_json`, without changing the response contract expected by the UI.

### Transcripts Storage Refactor (Phase G – JSON → Postgres)
- Introduced a dedicated `analytics.session_transcripts` table and
  `api.session_transcripts` view in `setup/schema.sql` to make per-session
  transcripts first-class citizens in the analytics Postgres database:
  - Columns: `user_id`, `session_id`, `created_at`, `updated_at`,
    `transcript_lines text[]`, and `transcript_json jsonb`.
  - Indexes on `(session_id)` and `(user_id, created_at DESC)` support
    efficient lookup by session and timeline queries per user.
- Updated `orchestrator/feedback_session/__init__.py` so `_load_transcript` now
  prefers the Postgres transcript when present, using `analytics_db.get_connection`
  to read from `analytics.session_transcripts` and falling back to the legacy
  blob-based `sessions/{sessionId}/transcript.json` document when the analytics
  database is unavailable or no transcript row exists.
- Extended `orchestrator/tests/test_session_endpoints.py` with a
  `test_load_transcript_prefers_db_when_available` case that patches
  `feedback_session.get_connection` and verifies that `_load_transcript`
  returns DB-provided `transcript_lines` without touching blob storage in the
  happy path.

### Transcripts Writer (Phase G4 – Runtime Path)
- Updated the Session UI `completeSession` handler (`ui/app/session/page.tsx`) to
  send the accumulated `transcript` array together with `sessionId` to
  `/api/orchestrator/session/complete`, so the backend can persist the final
  transcript.
- Extended `orchestrator/session_complete/__init__.py` to:
  - Accept an optional `transcript` field in the JSON body.
  - Write a `sessions/{sessionId}/transcript.json` blob document shaped as
    `{ "session_id": ..., "transcript": [...] }` for compatibility with
    existing blob-based tooling.
  - Insert a row into `analytics.session_transcripts` using
    `analytics_db.get_connection`, storing both `transcript_lines` and a
    `transcript_json` JSONB payload, while treating failures as best-effort and
    not affecting the 204 response.
- Added `test_session_complete_persists_transcript_to_blob_and_db` in
  `orchestrator/tests/test_session_endpoints.py` to verify that when a
  transcript is provided, `session_complete` writes both `session.json` and
  `transcript.json` and attempts an `INSERT INTO analytics.session_transcripts`
  with the expected parameters.
