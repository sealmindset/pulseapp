You are a senior visual architect and diagram designer.

Your task: **Create a detailed architecture diagram** for the “PULSE AI Training & Certification Platform” that uses the ATTACHED IMAGE as a reference for **style and layout only**, but strictly reflects the **exact components and connections listed below**.

> CRITICAL:  
> - Do **NOT** introduce any components, tools, services, or layers that are not explicitly listed in this prompt.  
> - Do **NOT** invent vector databases, RAG platforms, external tools, or new Azure resources.  
> - Stay fully within the infrastructure and architecture described here.

---

## 1. Visual Style (match the attached reference)

Use the attached “AI Agent Production Architecture” image as a style template:

- A bold title at the top (e.g., **“PULSE AI TRAINING & CERTIFICATION ARCHITECTURE”**).
- Rectangular **modules/sections** with titles (similar to “Memory”, “Security”, “Deployment”, etc. in the reference).
- Simple icons or small logos inside boxes for key services (e.g., Azure icons where applicable).
- Clear directional connectors (arrows) between boxes.
- A **data flow legend** strip at the bottom, similar to the reference, with 4 line styles:
  - **Blue solid arrows**: Primary training + scoring data flow.
  - **Black solid arrows**: Infrastructure / support connections.
  - **Orange solid arrows**: Feedback loops (insights that improve prompts or training flows).
  - **Black dashed arrows**: Direct read‑only access (e.g., admins viewing logs/telemetry).

The style should feel modern and similar in density and layout to the attached example, but all labels and components must come from the sections below.

---

## 2. High‑Level Layout (top‑to‑bottom)

Arrange the diagram roughly in these vertical zones:

1. **Top**: Users & Roles and Input Flows.
2. **Upper‑middle**: UI layer and Next.js API proxy layer.
3. **Middle**: Azure Function App orchestrator + admin APIs.
4. **Right‑middle**: Azure OpenAI and Storage.
5. **Left‑middle**: Virtual network, subnets, private endpoints, private DNS.
6. **Lower‑right**: Observability (Log Analytics, Application Insights).
7. **Bottom**: Outputs & evaluation (feedback to trainees, analytics to leaders) and the data flow legend.

---

## 3. Boxes (Modules) and Their Contents

Create labeled boxes (like in the reference image) for the following modules. Use **exact names and relationships** as described.

### 3.1 Users & Roles (top left)

Title: **Users & Roles**

Inside this box, show three items (can be icons + labels):

- **Trainees / Associates**  
- **Trainers / Coaches**  
- **Admins / Content Designers**

From this box, draw:

- A **blue primary arrow** from **Trainees / Associates** to the **UI Layer** box (section 3.2).
- A **blue or black arrow** from **Trainers / Coaches** to an **Outputs & Analytics** box (section 3.7).
- A **blue or black arrow** from **Admins / Content Designers** to the **Admin UI & APIs** box (section 3.3).

### 3.2 UI Layer (Next.js Web App)

Title: **UI Layer – Next.js Web App (app-PULSE-training-ui-<env>)**

Inside the box, list:

- **Pre‑Session Page** – start session, choose persona.
- **Session Page** – realtime audio interaction.
- **Feedback Page** – view scores and coaching.
- **Admin Page (Dev Mode Only)** – prompts & agents editor.

Connections:

- **Blue primary arrows** from **Trainees / Associates** into this UI Layer.
- **Blue arrows** from this UI Layer to the **Next.js API Proxies** box (3.3), labeled:
  - `POST /session/start`
  - `POST /audio/chunk`
  - `POST /session/complete`
  - `GET /feedback/{sessionId}`
- **Blue arrows** from the Admin part of the UI to Admin proxies:
  - `/admin/agents`
  - `/admin/prompts`
  - `/admin/prompts/{id}`
  - `/admin/prompts/{id}/versions`
  - `/admin/prompts/{id}/versions/{version}`

### 3.3 Next.js API Proxies (XHR Only)

Title: **Next.js API Proxies (XHR Only)**

Inside the box, group routes:

- **Training APIs (to orchestrator)**  
  - `/api/orchestrator/session/start`  
  - `/api/orchestrator/audio/chunk`  
  - `/api/orchestrator/session/complete`  
  - `/api/orchestrator/feedback/{sessionId}`

- **Admin APIs (dev‑mode)**  
  - `/api/orchestrator/admin/agents`  
  - `/api/orchestrator/admin/prompts`  
  - `/api/orchestrator/admin/prompts/[id]`  
  - `/api/orchestrator/admin/prompts/[id]/versions`  
  - `/api/orchestrator/admin/prompts/[id]/versions/[version]`

Connections:

- **Blue arrows** from this box to the **Azure Function App Orchestrator** box (3.4), labeled with the same paths but mapped to the Function App endpoints:
  - `/session/start`
  - `/audio/chunk`
  - `/session/complete`
  - `/feedback/{sessionId}`
  - `/admin/agents`
  - `/admin/prompts`
  - `/admin/prompts/{id}`
  - `/admin/prompts/{id}/versions`
  - `/admin/prompts/{id}/versions/{version}`

### 3.4 Azure Function App – Scenario Orchestrator & Admin APIs

Title: **Azure Function App – Scenario Orchestrator**  
Subtitle inside the box: `func-PULSE-training-scenario-<env>`

Inside, clearly distinguish:

- **Training endpoints (expected)**  
  - `/session/start` – start PULSE session and create `sessionId`.  
  - `/audio/chunk` – receive 1‑second audio chunks, perform ASR + persona response.  
  - `/session/complete` – finalize transcript and trigger scoring.  
  - `/feedback/{sessionId}` – return scoring JSON and artifacts.

- **Admin endpoints (implemented)**  
  - `/admin/agents` – read/update agent config (BCE/MCF/CPO, orchestrator).  
  - `/admin/prompts` – list/create prompts.  
  - `/admin/prompts/{id}` – get/update/delete prompt.  
  - `/admin/prompts/{id}/versions` – list versions.  
  - `/admin/prompts/{id}/versions/{version}` – view a specific version.

- **Shared logic**  
  - Uses shared blob helpers for:
    - `agents.json`.  
    - `prompts/{id}.json`.  
    - `prompts/{id}/versions/{n}.json`.  
  - Uses shared HTTP helpers for JSON responses and CORS.

Connections:

- **Blue arrows** from this box to:
  - **Azure OpenAI Account & Deployments** (3.5) – labeled “LLM calls for simulation & scoring”.
  - **Storage Account & Containers** (3.6) – labeled:
    - `AzureWebJobsStorage` (functions state & bindings).
    - `certification-materials` (training assets).
    - `interaction-logs` (session artifacts & logs).

- **Black arrows** to **Virtual Network & Subnets** (3.5 / 3.8) to indicate VNet integration and routing through private endpoints.

### 3.5 Azure OpenAI – Cognitive Account & Deployments

Title: **Azure OpenAI – Cognitive Account & Deployments**

Inside this box, show:

- Account: `cog-PULSE-training-<env>`
- Deployments:
  - `Persona-Core-Chat`
  - `Persona-High-Reasoning`
  - `PULSE-Audio-Realtime`
  - `Persona-Visual-Asset`

Connections:

- **Blue arrows** from the **Function App** (3.4) to this box, labeled:
  - “Persona simulation, coaching, and scoring”.
- **Black arrows** from this box to:
  - **Private Endpoint: Azure OpenAI** (in the VNet/Private Endpoints box, 3.8).
  - **Log Analytics Workspace** (3.9), labeled:
    - `diag_openai (Audit, RequestResponse)`.

### 3.6 Storage Account & Containers

Title: **Azure Storage – Training Data & Logs**

Inside:

- Storage Account: `sa-<name>`
- Containers:
  - `certification-materials`
  - `interaction-logs`
- Note (text inside box): “Also hosts agents.json, prompts/{id}.json, and prompt versions.”

Connections:

- **Blue arrows** from the **Function App** (3.4) to this box, labeled:
  - `AzureWebJobsStorage`
  - `Prompt & agent JSON`
  - `Session artifacts / logs`
- **Black arrows** from this box to:
  - **Private Endpoint: Storage Blob** (3.8).
  - **Log Analytics Workspace** (3.9), labeled:
    - `diag_storage (StorageRead/Write/Delete)`.

### 3.7 Outputs & Consumers

Title: **Outputs & Consumers**

Inside, create three small sub‑boxes:

- **Trainee Feedback & Certification**
  - Overall PULSE score (0–100).
  - Pass/Fail certification status.
  - BCE/MCF/CPO breakdown and coaching notes.
- **Trainer / Coach Review**
  - Access to transcripts and scorecards.
  - Human review labels:
    - Correct/Incorrect certification.
    - Major vs Minor hallucination issues.
- **Leadership & Analytics**
  - Aggregated views of PULSE mastery and performance (conceptual).

Connections:

- **Blue arrows** from the **Function App** (3.4) and **UI Layer** (3.2) into this Outputs box.
- **Orange arrows** from this Outputs box back to:
  - **Admins / Content Designers** (via Admin UI & APIs in 3.3/3.4), labeled:
    - “Feedback for prompt and scenario tuning.”

### 3.8 Network & Private Connectivity

Title: **Azure Network & Private Endpoints**

Inside show:

- **Virtual Network**: `vnet-PULSE-training-<env> (10.10.0.0/16)`
- **Subnets**:
  - `PULSE-app-subnet (10.10.1.0/24)` – hosting:
    - App Service Plan `asp-PULSE-training-<env>`.
    - Web App `app-PULSE-training-ui-<env>`.
    - Function App `func-PULSE-training-scenario-<env>`.
  - `PULSE-private-endpoints-subnet (10.10.2.0/24)` – hosting:
    - Private Endpoint: Azure OpenAI.
    - Private Endpoint: Storage Blob.
    - Private Endpoint: Web App (optional).

- **Private DNS Zones**:
  - `privatelink.openai.azure.com`
  - `privatelink.blob.core.windows.net`
  - `privatelink.azurewebsites.net (optional)`

Connections:

- **Black solid arrows**:
  - From Web App and Function App to the VNet (show VNet integration / Swift connections).
  - From VNet to each Private Endpoint.
  - From each Private Endpoint to its corresponding service (Azure OpenAI account, Storage account, optional Web App endpoint).
  - From Private DNS Zones to the VNet (vnet link).

### 3.9 Observability – Logs & Telemetry

Title: **Observability – Log Analytics & Application Insights**

Inside show:

- **Log Analytics Workspace**: `law-PULSE-training-<env>`
- **Application Insights**: `appi-PULSE-training-<env>`

Connections:

- **Black arrows** from:
  - Azure OpenAI account → Log Analytics (label: `diag_openai (Audit, RequestResponse)`).
  - Storage account → Log Analytics (label: `diag_storage (StorageRead/Write/Delete)`).
  - Web App → Log Analytics (label: `diag_webapp (HTTPLogs, ConsoleLogs)`).
  - Function App → Log Analytics (label: `diag_functionapp (FunctionAppLogs, AppServiceHTTPLogs)`).
- **Black arrows** from:
  - Web App → Application Insights (label: `AppInsights`).
  - Function App → Application Insights (label: `AppInsights`).
- **Black dashed arrows** from this Observability box to:
  - **Trainers / Coaches** (reviews and coaching insight).
  - **Admins / Content Designers** (prompt and scenario design insight).
  - **Leadership & Analytics** (leaders viewing aggregated metrics).

These dashed arrows represent **read‑only access to logs and telemetry**, not additional services.

---

## 4. Data Flow Legend (Bottom Strip)

At the bottom of the diagram, create a legend bar similar to the attached image with four line styles:

- **Primary Training & Scoring Flow** – blue solid arrow.
- **Infrastructure / Support Connections** – black solid arrow.
- **Feedback Loops (Human Oversight & Tuning)** – orange solid arrow.
- **Direct Read‑Only Access** – black dashed arrow.

---

## 5. Non‑Negotiable Constraints

- Do **not** add any services or boxes beyond what is explicitly listed above.  
- Do **not** add vector databases, RAG/knowledge platforms, third‑party tools, or additional clouds.  
- Keep all service names, labels, and flows consistent with the descriptions in this prompt.  
- The goal is a **single, comprehensive, easy‑to‑read diagram** that mirrors the layout style of the attached image while staying 100% faithful to the PULSE architecture described here.