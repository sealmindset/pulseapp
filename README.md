# PULSE Behavioral Certification Platform

Secure Azure Terraform IaC + Next.js UI/UX

## Overview
This repository provisions a secure, production-ready Azure foundation for the PULSE Behavioral Certification Platform and includes a Next.js UI/UX for persona-driven sales training. The architecture emphasizes RESTRICTED IP protection, network isolation with Private Link, and observability.

Highlights:
- Azure resources provisioned via Terraform (AzureRM v4).
- Azure OpenAI with multiple model deployments (chat, reasoning, audio realtime, visual asset) over Private Endpoints (no public access).
- Storage Account with private containers and no public access.
- App Service Plan, Web App (UI), and Function App (orchestrator) with VNet integration.
- Private DNS Zones wired to Private Endpoints (openai, blob, azurewebsites when enabled).
- Logging/monitoring via Log Analytics and Application Insights.
- Next.js UI/UX with persona selection, session flow with XHR audio chunking, avatar rendering, and feedback display.

## PULSE Selling Framework

The AI Trainer is built around a conversational framework called **PULSE Selling**.

**PULSE** is a 5-step structure for high-quality customer conversations:

- **P – Probe**  
  Open the conversation, build quick rapport, and ask smart, open-ended questions that reveal context fast.

- **U – Understand**  
  Go beyond surface requests to uncover true needs, constraints, and emotions. Reflect back what you heard and verify you understood correctly.

- **L – Link**  
  Connect recommendations directly to what the customer said, using their language. Make it clear how each option maps to their specific goals and pains.

- **S – Simplify**  
  Reduce friction and confusion by narrowing choices, explaining trade-offs in plain language, and addressing common objections without overwhelming the customer.

- **E – Earn**  
  Make a professional recommendation based on everything you learned, then earn a clear commitment: a decision, a scheduled follow-up, or the next concrete step.

### How the Trainer uses PULSE

During each simulated conversation, the AI Coach evaluates the associate against the PULSE steps:

- Did they **Probe** with meaningful, open-ended questions?
- Did they **Understand** the customer’s real situation and emotions?
- Did they **Link** recommendations clearly to the customer’s words?
- Did they **Simplify** choices instead of overwhelming the customer?
- Did they **Earn** a committed next step?

After the session, the Trainer returns:

- A **score** for each PULSE step (e.g. 0–3)
- A brief **reason** for the score
- 1–2 **coaching tips** on how to improve that part of the conversation next time

This turns abstract “soft skills” into concrete, coachable behaviors while keeping the associate focused on a simple, memorable structure: **Probe → Understand → Link → Simplify → Earn**.

## Environments
Terraform supports multiple environments via the `environment` variable. Defaults to `prod`.
- prod (default)
- staging (example)

Use a `*.tfvars` to pass environment-specific values.

## Prerequisites
Tooling:
- Terraform ≥ 1.6
- Azure CLI ≥ 2.55 (`az version`)
- Node.js 18 LTS and npm (for UI at `/ui`)
- Optional for diagram generation: Python 3.10+, `graphviz` binaries, and `diagrams` Python package

Azure requirements:
- Active Azure subscription with the following permissions on the target subscription or resource group:
  - Owner (recommended for bootstrap) or Contributor
  - Network Contributor (VNet, Private Endpoints)
  - Private DNS Zone Contributor (private DNS zones + links)
  - DNS Zone Contributor (if managing DNS zones)
  - Application Insights Component Contributor (optional)
- Resource providers registered (run once per subscription):
  ```bash
  az account set --subscription <SUBSCRIPTION_ID>
  az provider register --namespace Microsoft.CognitiveServices
  az provider register --namespace Microsoft.Network
  az provider register --namespace Microsoft.Web
  az provider register --namespace Microsoft.OperationalInsights
  az provider register --namespace Microsoft.Insights
  az provider register --namespace Microsoft.Storage
  ```
- Azure OpenAI access approved for your subscription/region and sufficient quota for the selected models/SKUs.

Security posture:
- Azure OpenAI and Storage: `public_network_access_enabled = false`, reachable only via Private Endpoints + Private DNS.
- Web App and Function App: VNet integration; Web App Private Endpoint toggle via variable (default enabled).
- CORS: Open on the orchestrator API surface to enable the browser UI to call through a proxy (UI ↔ Function App via XHR).

## Repository Structure
- `/main.tf`, `/variables.tf`, `/outputs.tf` — Terraform IaC
- `/docs/PULSE_network_diagram.py` — Optional Azure topology diagram generator (PNG+SVG or draw.io `.drawio`)
- `/ui` — Next.js UI/UX (App Router, TypeScript, Tailwind)

## Terraform: Configuration
Key variables (see `variables.tf` for full list and defaults):
- `environment` — prod/staging
- `location` — Azure region (default: East US 2)
- `resource_group_name` — Resource group name (default: `rg-PULSE-training-prod`)
- `project_name` — Short project name used in resource naming (`PULSE-training`)
- `owner` — Tagging owner/business unit (required)
- `storage_account_name` — Globally unique Storage Account name (required)
- `openai_*` — Model IDs/versions, deployment SKUs and capacity
- `behavioral_mastery_threshold` — Must be between 0.85–1.0 (default 0.85)
- `enable_webapp_private_endpoint` — Toggle Web App Private Endpoint (default true)
- `web_app_linux_fx_version` — Runtime (default `NODE|18-lts`)
- Analytics PostgreSQL (longitudinal & readiness):
  - `analytics_pg_subnet_prefix` — CIDR for analytics Postgres subnet (default `10.10.3.0/24`)
  - `analytics_pg_version` — Postgres engine version (default `16`)
  - `analytics_pg_sku_name` — Flexible Server SKU for analytics (default `GP_Standard_D2s_v3`)
  - `analytics_pg_storage_mb` — Storage in MB (default `32768`)
  - `analytics_pg_backup_retention_days` — Backup retention in days (default `7`)
  - `analytics_pg_admin_username` — Admin username for analytics Postgres (required)
  - `analytics_pg_admin_password` — Admin password for analytics Postgres (required, sensitive)

Example `prod.tfvars`:
```hcl
environment               = "prod"
location                  = "East US 2"
resource_group_name       = "rg-PULSE-training-prod"
project_name              = "PULSE-training"
owner                     = "Sales Excellence"
storage_account_name      = "PULSEtrainingprodsa123"
behavioral_mastery_threshold = 0.9
enable_webapp_private_endpoint = true
```

## Terraform: Deploy
1) Login and select subscription
```bash
az login
az account set --subscription <SUBSCRIPTION_ID>
```

2) Initialize
```bash
terraform init
```

3) Plan
```bash
terraform plan -var-file=prod.tfvars -out=tfplan
```

4) Apply
```bash
terraform apply tfplan
```

Outputs include hostnames/endpoints for the Web App and Function App. These are used by the UI `.env.local`.

Notes:
- State is local by default. For teams, configure a remote backend (e.g., Azure Storage) in Terraform before applying.
- Private Endpoints create private IPs and DNS zone links; ensure the VNet address spaces do not overlap with existing corporate networks.

## UI/UX: Setup and Run (Next.js)
The UI in `/ui` communicates with the orchestrator Function App using XHR proxy routes. During local development, point the UI to the cloud Function App created by Terraform.

1) Create environment file
```bash
cp ui/.env.example ui/.env.local
```
Set values in `ui/.env.local`:
- `FUNCTION_APP_BASE_URL=https://<your-function-app>.azurewebsites.net`
- Optional: `NEXT_PUBLIC_ENV_NAME=local`
- Optional: `APPINSIGHTS_CONNECTION_STRING=` (server-side)
# To generate a hex string of 32 characters for JWT secret, run:
# LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom </dev/urandom | head -c 32; echo

2) Install dependencies and run
```bash
cd ui
npm install
npm run dev
```
Visit http://localhost:3000

3) Production build (optional)
```bash
npm run build
npm run start
```

UI features:
- Persona selection and scenario filters
- Session page with avatar rendering and real-time mic audio chunk upload over XHR
- Immediate audio playback from orchestrator responses (supports `audio/*`, `ttsUrl`, `audioBase64`)
- Transcript display and Complete Session action
- Feedback page fetching score, rubric, and artifacts by `sessionId`

## PULSE Trainer (Dev Preview)

The PULSE Trainer Agent is exposed via a dedicated Training page and is intended for **non-production** and controlled pilots.

- Path: `/training` (Next.js UI)
- Trainer endpoint: `POST /trainer/pulse/step` (Function App)

Gating:

- **UI:**
  - `NEXT_PUBLIC_ENABLE_TRAINING=true`
  - `NEXT_PUBLIC_ENV_NAME!=prod`
  - When enabled, the Training nav link appears and the `/training` page is active; when disabled, the page shows a simple notice.
- **Orchestrator:**
  - `PULSE_TRAINER_ENABLED=true` — required for the trainer function to call Azure OpenAI.
  - When unset/false, the trainer returns a static-evaluation JSON `OUTPUT` indicating that training is disabled in this environment.

Azure OpenAI requirements (in addition to the Terraform-provisioned settings):

- `AZURE_OPENAI_API_KEY` — Azure OpenAI API key for the configured endpoint.
- Deployed chat models referenced by:
  - `OPENAI_ENDPOINT`
  - `OPENAI_API_VERSION`
  - `OPENAI_DEPLOYMENT_PERSONA_HIGH_REASONING` or `OPENAI_DEPLOYMENT_PERSONA_CORE_CHAT`

The trainer is wired to the PULSE Selling framework and returns structured JSON for adaptive questioning, mastery estimates, and (optionally) self-annealing trainer change logs. In production environments, keep the trainer **disabled by default** and enable it only in explicitly approved scenarios.

## Admin (Dev Mode Prompt Editor)
- Path: `/admin` (visible only when `NEXT_PUBLIC_ENABLE_ADMIN=true` and `NEXT_PUBLIC_ENV_NAME!=prod`)
- Purpose: Edit agent configs and prompts during development without authentication. Hidden in production.
- UI features:
  - Tabs: Prompts | Agents
  - Prompts: list/search, view/edit/create/delete, view versions (opens version content via link)
  - Agents: simple table editor with add/remove and save
- Next.js proxy routes (XHR, open CORS) to the orchestrator:
  - `GET/PUT   /api/orchestrator/admin/agents`
  - `GET/POST  /api/orchestrator/admin/prompts`
  - `GET/PUT/DELETE /api/orchestrator/admin/prompts/{id}`
  - `GET      /api/orchestrator/admin/prompts/{id}/versions`
  - `GET      /api/orchestrator/admin/prompts/{id}/versions/{version}`
- Function App requirements (server-side implementation expected):
  - Mirror the above endpoints under `/admin/*` and guard with `ADMIN_EDIT_ENABLED=true` for write ops in dev.
  - Persist to Azure Storage (private container), e.g., `prompts/` and `agents.json` with versioned prompt copies.
  - Disable or require auth for write ops in production.

Important:
- Because Azure OpenAI/Storage are private-only, local UI cannot call them directly. Always route via the Function App.
- The UI’s internal API routes proxy to the orchestrator and emit permissive CORS headers as required.

## Orchestrator Function App
Terraform creates a Function App (Linux) with VNet integration to access private resources. Deploy the orchestrator code via your preferred CI/CD (zip deploy, GitHub Actions, etc.). The UI expects the Function App to expose routes such as:
- `POST /session/start`
- `POST /audio/chunk`
- `POST /session/complete`
- `GET  /feedback/{sessionId}`

Admin endpoints (implemented in `/orchestrator`):
- `GET/PUT   /admin/agents`
- `GET/POST  /admin/prompts`
- `GET/PUT/DELETE /admin/prompts/{id}`
- `GET      /admin/prompts/{id}/versions`
- `GET      /admin/prompts/{id}/versions/{version}`

Analytics & Readiness
--------------------

- `PULSE_ANALYTICS_ENABLED` — when `true/1/yes`, enables writing session scorecard events into the analytics Postgres `session_events` table.
- `PULSE_READINESS_ENABLED` — when `true/1/yes`, enables the readiness aggregation service to compute `user_skill_agg` and `user_readiness` snapshots for users with a valid `user_id`.

Function App settings (dev mode):
- `ADMIN_EDIT_ENABLED=true` (enables write ops on admin endpoints in dev)
- `PROMPTS_CONTAINER=prompts` (optional; defaults to `prompts`)
- Storage connection string: one of is required
  - `BLOB_CONN_STRING` or `AZURE_STORAGE_CONNECTION_STRING` or `AzureWebJobsStorage`
 - Analytics Postgres (longitudinal + readiness):
   - `PULSE_ANALYTICS_DB_HOST`, `PULSE_ANALYTICS_DB_PORT`, `PULSE_ANALYTICS_DB_NAME`, `PULSE_ANALYTICS_DB_USER`, `PULSE_ANALYTICS_DB_PASSWORD`
   - These are populated by Terraform from the analytics Postgres Flexible Server and are intended for Longitudinal Analytics Store and Readiness Score schemas (e.g., `session_events`, `user_skill_agg`, `user_readiness`).
  - Analytics / Readiness feature flags (pilot):
    - `PULSE_ANALYTICS_ENABLED` — when `true/1/yes`, enables writing session
      scorecard events into the analytics Postgres `session_events` table.
    - `PULSE_READINESS_ENABLED` — when `true/1/yes`, enables the readiness
      aggregation service to compute `user_skill_agg` and `user_readiness`
      snapshots for users with a valid `user_id`.

Identity and pilot user_id configuration:
- The orchestrator extracts an optional `userId`/`user_id` from the
  `/session/start` request body (or an `X-PULSE-User-Id` header), validates it
  as a UUID, and persists it into the session document as `user_id` when
  present.
- Readiness aggregation only runs when a valid UUID `user_id` is available,
  ensuring snapshots are always tied to a stable learner identity.
- For pilots without a full auth stack, the Pre-Session UI can be configured to
  send a fixed UUID per learner by setting:
  - `NEXT_PUBLIC_PULSE_USER_ID` (preferred), or
  - `NEXT_PUBLIC_PULSE_READINESS_USER_ID` (also used by the Feedback
    Readiness card).

Quick tests (replace base URL):
```bash
BASE="https://<function-app>.azurewebsites.net"
curl -s "$BASE/admin/prompts" | jq .
curl -s -X POST "$BASE/admin/prompts" -H 'Content-Type: application/json' \
  -d '{"title":"Test System Prompt","type":"system","content":"You are an agent.","agentId":"agent-1"}' | jq .
curl -s "$BASE/admin/prompts/<prompt-id>" | jq .
curl -s -X PUT "$BASE/admin/prompts/<prompt-id>" -H 'Content-Type: application/json' -d '{"content":"Updated"}' | jq .
curl -s "$BASE/admin/prompts/<prompt-id>/versions" | jq .
```

## Optional: Network Diagram
Generate PNG and SVG topology diagrams from `/docs`:
```bash
python3 docs/PULSE_network_diagram.py --tf-path . --output-basename PULSE-network-diagram --direction LR
```

Generate draw.io XML for Lucidchart/draw.io import:
```bash
python3 docs/PULSE_network_diagram.py --tf-path . --drawio --output-basename PULSE-network-diagram
```

Requires Graphviz and `diagrams` package.

## Analytics Schema (Quick Reference)

The analytics PostgreSQL database (`pulse_analytics`) is provisioned by
Terraform, but its tables are owned by the application so they can evolve via
normal migrations.

- Canonical DDL lives in `setup/schema.sql` and creates:
  - `analytics.session_events` — per-session / per-skill events.
  - `analytics.user_skill_agg` — rolling aggregates per user/skill/window.
  - `analytics.user_readiness` — readiness snapshots over time.
  - `api.*` views that expose numeric `id` (from `api_id`) for PostgREST while
    preserving UUIDs for internal joins.
- To apply the schema to a fresh analytics database, use the analytics
  connection vars exported to the Function App/Web App:

  ```bash
  export PULSE_ANALYTICS_DB_HOST="<server>.postgres.database.azure.com"
  export PULSE_ANALYTICS_DB_NAME="pulse_analytics"
  export PULSE_ANALYTICS_DB_USER="<user>"
  export PULSE_ANALYTICS_DB_PASSWORD="<password>"

  psql "postgres://$PULSE_ANALYTICS_DB_USER:$PULSE_ANALYTICS_DB_PASSWORD@$PULSE_ANALYTICS_DB_HOST:5432/$PULSE_ANALYTICS_DB_NAME" \
    -f setup/schema.sql
  ```

Once schema is applied and the `PULSE_ANALYTICS_ENABLED` /
`PULSE_READINESS_ENABLED` flags are set, the orchestrator will begin writing
scorecard events and computing readiness snapshots (when a valid `user_id`
is available on sessions), and the optional Readiness card on the Feedback
page can be enabled via `NEXT_PUBLIC_PULSE_READINESS_USER_ID`.

## Troubleshooting
- 403/404 from Function App: Confirm `FUNCTION_APP_BASE_URL` and that the orchestrator is deployed and reachable.
- Model deployment errors: Verify Azure OpenAI provider access/quota and that the target region is supported for your subscription.
- Private DNS resolution: Ensure Private DNS zone links are created/propagated and the App Service is correctly VNet-integrated.
- UI cannot fetch feedback after refresh: `sessionId` is in memory; start a new session from Pre-Session or persist ID if desired.

## Security Notes
- Azure AI and Storage are not publicly accessible; access is via Private Link only.
- Web and Function Apps are VNet-integrated; the Web App can also use a Private Endpoint (default enabled).
- Function App CORS is open to allow browser XHR; protect sensitive data on the server only and avoid logging IDs on the client.

## License

This project is released under a **dual-licensing** model:

### Community Edition – AGPL-3.0

The core of this project is licensed under the **GNU Affero General Public License v3.0 (AGPL-3.0)**.

In practical terms, this means:

- You can **use, modify, and redistribute** the code, including for commercial purposes.
- If you **modify** the code and make it available to others **or** run it as a **networked service (SaaS)**, you must:
  - Provide access to the **source code** of your modified version, and  
  - Keep it under the **AGPL-3.0** license.

See the full license text in the [`LICENSE`](./LICENSE) file for details.

### Commercial License

If your organization:

- Wants to integrate this project into a **closed-source** product or platform,
- Plans to offer it as a **hosted service** without sharing modifications, or
- Requires different **legal / compliance** terms than AGPL-3.0 allows,

a **commercial license** is available.

Commercial licensing typically includes:

- The right to **use and modify** the software **without** the copyleft/AGPL obligations  
- Optional **support**, **feature prioritization**, and **integration guidance**

For commercial licensing, support, or custom engagements, please contact:

> **Author:** Robert Vance  
> **Email:** ravance@gmail.com
> **Subject:** “PULSE Trainer – Commercial License Inquiry”

---

**Summary**

- **Individual developers, researchers, and open-source teams**: use AGPL-3.0.  
- **Companies wanting proprietary use or SaaS without sharing changes**: reach out for a commercial license.
