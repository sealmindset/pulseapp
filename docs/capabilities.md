# PULSE Platform Capabilities

This document provides a comprehensive overview of all capabilities implemented in the PULSE Behavioral Certification Platform.

---

## 1. Core Vocalization and Audio Capabilities

The platform provides full vocalization support essential for creating immersive and interactive sales training environments. This capability is enabled by **Azure OpenAI audio models** that support real-time conversational interaction.

### 1.1 Azure OpenAI Audio Models

*   **Real-Time Conversational Models:** The platform leverages **GPT-4o audio models** supporting **"low-latency, speech in, speech out conversational interactions"**. Specific models like `gpt-4o-realtime-preview` enable real-time audio processing.
*   **Speech-to-Text (Trainee Input):** Models including **`whisper`** and **`gpt-4o-transcribe`** provide high-quality speech-to-text conversion, enabling the Agentic AI system to process and evaluate trainee verbal performance.
*   **Text-to-Speech (AI Persona Output):** Models like `tts` and `tts-hd` generate realistic, persona-driven spoken responses with configurable voice styles and tones.

### 1.2 PULSE Behavioral Training Support

Vocalization enables training on verbal communication tactics required for H4 (High Mastery):

*   **Proprietary Language Practice:** Trainees practice "mini-talks" (concise product explanations) and frameworks like **CECAP** (Compliment, Empathy, Can Do, Ask, Positivity) and **LERA** (Listen, Empathize, Reaffirm, Add Relevant Information).
*   **Behavioral Adaptation:** AI personas based on the **Platinum Rule** require trainees to adapt vocal style (pace, tone) to match customer personality types (Director uses assertive tone; Thinker uses monotone, calm, measured voice).
*   **Pronunciation Training:** Audio clips for specific terminology (e.g., "lyocell," "percale," "Supima") ensure correct vocal delivery.

### 1.3 Complete Audio Processing Pipeline

The orchestrator implements a full end-to-end audio processing pipeline:

1. **Speech-to-Text (STT):** User audio captured via MediaRecorder is transcribed using `gpt-4o-realtime-preview`
2. **Conversational AI:** Transcripts processed by chat models with persona-aware prompting
3. **Text-to-Speech (TTS):** AI responses synthesized into natural speech
4. **Avatar Video:** Lip-synced video clips generated when available
5. **Conversation Persistence:** All exchanges stored in blob storage for evaluation

---

## 2. Avatar and Visual Systems

### 2.1 Dynamic Avatar Video Generation (Sora-2)

The platform supports **dynamic lip-synced avatar videos** using Azure OpenAI's Sora-2 model:

*   **Video vs Static Images:** Migrated from DALL-E-3 (static) to Sora-2 (video) for talking head avatars synchronized with TTS audio
*   **Persona-Specific Avatars:** Each Platinum Rule persona has distinct visual configuration:
    - **Director:** Professional business executive, formal attire, assertive demeanor
    - **Relater:** Warm friendly person, smart casual, patient and empathetic
    - **Socializer:** Energetic expressive person, trendy casual, enthusiastic
    - **Thinker:** Thoughtful analytical person, neat professional, methodical
*   **Emotion-Aware Expressions:** Avatar maps response content to facial expressions (neutral, interested, skeptical, pleased, concerned, excited, hesitant)
*   **Graceful Degradation:** Falls back to static images when Sora-2 unavailable

### 2.2 Avatar Manager Component

Located in `ui/components/avatar-manager.tsx`, the Avatar Manager provides:

*   **ModelScope Integration:** Local TTS avatar generation using ModelScope models
*   **Piper TTS Support:** Lightweight neural text-to-speech with voice model selection
*   **Azure Speech Avatar Service:** Production avatar service integration via `AZURE_SPEECH_REGION` and `AZURE_SPEECH_KEY`
*   **Multi-Provider Architecture:** Automatic provider selection based on availability and configuration

### 2.3 Scenario Configuration System

Scenarios configured in `ui/lib/scenarios/scenarioConfig.ts` define:

*   Persona type assignment (Director, Relater, Socializer, Thinker)
*   Voice selection and behavioral parameters
*   Customer background and conversation context
*   Evaluation rubric and mastery thresholds

---

## 3. Authentication and Identity Management

### 3.1 OIDC/SSO Integration with Azure AD

The platform implements enterprise-grade authentication:

*   **NextAuth.js Integration:** Full OIDC flow with Azure AD provider
*   **Configuration Variables:**
    - `AUTH_MODE`: Toggle between SSO and bypass modes
    - `AZURE_AD_CLIENT_ID`, `AZURE_AD_CLIENT_SECRET`, `AZURE_AD_TENANT_ID`
    - `NEXTAUTH_SECRET`, `NEXTAUTH_URL`
*   **Token Management:** Secure session handling with JWT tokens
*   **Middleware Protection:** Route protection via `middleware.ts` for authenticated paths

### 3.2 Five-Tier RBAC System

Implemented in `ui/lib/rbac.ts`, the Role-Based Access Control system defines:

| Role | Capabilities |
|------|-------------|
| **super_admin** | Full system access, user management, settings configuration |
| **admin** | Organization management, user invitations, reports access |
| **manager** | Team oversight, trainee progress tracking, analytics |
| **trainer** | Content delivery, session facilitation, feedback provision |
| **trainee** | Training participation, self-assessment, progress viewing |

### 3.3 User Management System

Located in `ui/app/admin/users/`:

*   **User Directory:** Paginated list with search and role filtering
*   **Role Assignment:** Dropdown selection with immediate save
*   **User Status:** Active/inactive toggle with visual indicators
*   **Audit Trail:** Last login tracking and activity monitoring

### 3.4 User Invitation System

Two invitation methods implemented:

*   **Email Invitations:** Direct email with secure invitation link and role pre-assignment
*   **Shareable Links:** Generated links with configurable expiration and usage limits
*   **Domain Auto-Provisioning Rules:** Automatic role assignment based on email domain patterns

---

## 4. Training Administration

### 4.1 Training Admin Dashboard

Located at `ui/app/admin/training/page.tsx`, the dashboard provides four tabs:

| Tab | Description |
|-----|-------------|
| **Modules** | Training module management, ordering, and activation |
| **Levels** | Certification level configuration and prerequisites |
| **Settings** | Global training parameters and thresholds |
| **Analytics** | Training metrics and completion statistics |

### 4.2 Admin Prompt Editor

Gated to non-production environments (`NEXT_PUBLIC_ENABLE_ADMIN=true`):

*   **Prompt Versioning:** Per-version snapshots with rollback capability
*   **System Prompt Management:** Create, view, edit versioned prompts
*   **Agent Definitions:** Configure AI agent behaviors and parameters
*   **Storage:** Private Azure Blob container with version history

### 4.3 Trainer Self-Annealing

When configured, the PULSE Trainer emits `trainer_change_log` entries:

*   Captures observed patterns and proposed rubric adjustments
*   Feedback channel for human prompt refinement
*   Server-side storage behind private networking

---

## 5. PULSE Framework Agents

### 5.1 PULSE Trainer Agent

Provides step-focused coaching for the PULSE Selling framework:

*   **Training Flow:** `/training` page calls backend trainer endpoint (`POST /trainer/pulse/step`)
*   **Structured Input:** CONFIG and SESSION JSON with PULSE step, scenario rubric, learner answer
*   **Adaptive Behavior:**
    - Diagnose strengths/weaknesses per PULSE step
    - Ask targeted follow-up questions when adaptive training enabled
    - Estimate step-level mastery
*   **Environment Gating:**
    - UI: `NEXT_PUBLIC_ENABLE_TRAINING=true` and `NEXT_PUBLIC_ENV_NAME!=prod`
    - Backend: `PULSE_TRAINER_ENABLED=true`

### 5.2 PULSE Evaluator/Coach

Scores completed conversations and provides structured feedback:

*   **PULSE 0-3 Scoring:** Five-step framework (Probe, Understand, Link, Simplify, Earn)
    - 0 = not demonstrated
    - 1 = weak
    - 2 = solid
    - 3 = strong
*   **Structured JSON Output:**
    - `framework: "PULSE"`
    - `scores` per step with `score`, `reason`, and `tips`
    - `overall_summary` with strengths and improvement opportunities
*   **Prompt Definition:** Canonical prompt in `docs/pulseagent.md`, managed as `pulse-evaluator-v1`

### 5.3 BCE/MCF/CPO Evaluation Agents

Specialized evaluation agents for different competency dimensions:

*   **BCE (Behavioral Certification Evaluator):** Assesses behavioral adaptation
*   **MCF (Mastery Certification Framework):** Measures skill progression
*   **CPO (Customer Persona Optimization):** Evaluates persona handling

---

## 6. Session and Feedback System

### 6.1 Pre-Session Configuration

Located at `ui/app/pre-session/page.tsx`:

*   **Scenario Selection:** Choose training scenario and persona type
*   **User ID Tagging:** Optional pilot user ID for analytics (`NEXT_PUBLIC_PULSE_READINESS_USER_ID`)
*   **Session Parameters:** Configure duration, difficulty, and focus areas

### 6.2 Live Session Page

The core training experience at `ui/app/session/`:

*   **Real-Time Audio:** MediaRecorder capture with chunked upload
*   **Avatar Display:** Visual feedback from AI persona
*   **Transcript View:** Live conversation display
*   **Session Controls:** Start, pause, end session actions
*   **Persistence:** Automatic save to blob storage

### 6.3 Multi-Tab Feedback Page

Located at `ui/app/feedback/page.tsx` with multiple analysis views:

| Tab | Content |
|-----|---------|
| **Summary** | Overall session performance overview |
| **PULSE Analysis** | Step-by-step PULSE framework scoring |
| **AI Coach** | Personalized improvement recommendations |
| **Transcript** | Full conversation with annotations |
| **Readiness** | Longitudinal skill readiness assessment |

### 6.4 Readiness Service Integration

API routes in `ui/app/api/orchestrator/readiness/`:

*   **User Readiness:** `GET /readiness/{userId}` - Overall readiness score
*   **Skill Breakdown:** `GET /readiness/{userId}/skills` - Per-skill readiness metrics
*   **Longitudinal Tracking:** Historical score progression
*   **Conditional Display:** Shown only when `NEXT_PUBLIC_PULSE_READINESS_USER_ID` configured

---

## 7. Analytics and Logging

### 7.1 PostgreSQL Analytics Database

Provisioned via `modules/analytics_postgres/`:

*   **Server:** Azure PostgreSQL Flexible Server (`pg-PULSE-analytics-{env}`)
*   **Database:** `pulse_analytics` with UTF8 encoding
*   **Networking:** Private subnet with delegated PostgreSQL access
*   **Private DNS:** `privatelink.postgres.database.azure.com` resolution
*   **Connectivity:** App settings provide `PULSE_ANALYTICS_DB_*` credentials

### 7.2 Application Insights Integration

*   **Connection String:** Provided via `APPLICATIONINSIGHTS_CONNECTION_STRING`
*   **Telemetry:** Request tracing, exception logging, performance metrics
*   **Dashboard:** Azure portal monitoring and alerting

### 7.3 Log Management (Cribl Integration)

Admin log management at `ui/app/admin/logs/`:

*   **Ingest Configuration:** Configurable log ingest URL
*   **Connection Testing:** `POST /api/admin/logs/test` endpoint
*   **Timeout Handling:** Connection timeout detection with user-friendly messaging

### 7.4 Admin Dashboard Overview

Main admin dashboard at `ui/app/admin/`:

*   **System Metrics:** Active users, session counts, completion rates
*   **Quick Actions:** Navigation to sub-admin features
*   **Status Indicators:** Service health and connectivity status

---

## 8. User Interface Capabilities

### 8.1 Dark/Light Mode Theme Toggle

Implemented in `ui/components/mode-toggle.tsx`:

*   **Theme Provider:** Next-themes integration for system-wide theming
*   **Toggle Component:** Dropdown menu with Light, Dark, and System options
*   **Persistence:** Theme preference stored in localStorage
*   **System Detection:** Automatic detection of OS preference when set to "System"
*   **Smooth Transitions:** CSS transitions for theme switching

### 8.2 Dropdown Menu Component

Located at `ui/components/ui/dropdown-menu.tsx`:

*   **Radix UI Foundation:** Built on @radix-ui/react-dropdown-menu
*   **Accessibility:** Full keyboard navigation and screen reader support
*   **Sub-menus:** Nested menu support with chevron indicators
*   **Checkboxes/Radio:** Selection state management
*   **Animation:** Smooth enter/exit animations

### 8.3 Component Library

Comprehensive UI components in `ui/components/ui/`:

*   **Forms:** Input, Select, Checkbox, Radio, Switch, Textarea
*   **Feedback:** Alert, Toast, Progress, Skeleton loaders
*   **Navigation:** Tabs, Breadcrumbs, Pagination
*   **Overlays:** Dialog, Drawer, Popover, Tooltip
*   **Data Display:** Table, Card, Badge, Avatar

---

## 9. Infrastructure and Networking

### 9.1 Private Endpoint Architecture

All sensitive services use private endpoints:

*   **Azure OpenAI:** Private endpoint with custom subdomain
*   **Azure Storage:** Private endpoint for blob access
*   **Azure PostgreSQL:** Private subnet with delegation
*   **Azure Speech:** Private endpoint when enabled

### 9.2 VNet Integration

*   **Application Subnet:** Web App and Function App VNet integration
*   **Service Subnet:** Private endpoint subnet
*   **Analytics Subnet:** PostgreSQL Flexible Server delegation
*   **NSG Rules:** Network security group restrictions

### 9.3 Multi-Deployment OpenAI Configuration

Four deployment types configured:

| Deployment | Purpose | Variable |
|------------|---------|----------|
| **Persona-Core-Chat** | Primary conversational AI | `OPENAI_DEPLOYMENT_PERSONA_CORE_CHAT` |
| **Persona-High-Reasoning** | Complex reasoning tasks | `OPENAI_DEPLOYMENT_PERSONA_HIGH_REASONING` |
| **PULSE-Audio-Realtime** | STT/TTS processing | `OPENAI_DEPLOYMENT_PULSE_AUDIO_REALTIME` |
| **Persona-Visual-Asset** | Image/video generation | `OPENAI_DEPLOYMENT_PERSONA_VISUAL_ASSET` |

---

## 10. Deployment and Operations

### 10.1 Terraform Infrastructure

Modular Terraform configuration:

*   **modules/app/:** Web App and Function App definitions
*   **modules/openai/:** Azure OpenAI account and deployments
*   **modules/storage/:** Blob storage with containers
*   **modules/analytics_postgres/:** PostgreSQL analytics database
*   **modules/speech/:** Azure Speech Services (optional)
*   **modules/monitoring/:** Application Insights and Log Analytics

### 10.2 Function App Orchestrator

Python-based Azure Function App (`func-PULSE-scenario-{env}`):

*   **Audio Processing:** `/audio/chunk` endpoint for real-time STT/TTS
*   **Trainer Endpoints:** PULSE step coaching and evaluation
*   **Readiness API:** User skill readiness calculations
*   **Scenario Processing:** Configurable via `SCENARIO_PROCESS_PIPELINE`

### 10.3 Next.js Web Application

Production web application (`app-PULSE-ui-{env}`):

*   **Server-Side Rendering:** Optimized page loads
*   **API Routes:** Proxy layer to Function App
*   **Static Assets:** Optimized delivery
*   **Environment Configuration:** Build-time and runtime variables

---

## 11. Security Features

### 11.1 Network Security

*   **HTTPS Enforcement:** `https_only = true` on all web resources
*   **Private Networking:** All AI and data services on private endpoints
*   **VNet Integration:** Application traffic stays within virtual network
*   **No Public Access:** `public_network_access_enabled = false` on sensitive resources

### 11.2 Identity Security

*   **System-Assigned Managed Identity:** Web App and Function App
*   **RBAC Integration:** Azure AD role assignments
*   **Secret Management:** Terraform variables for sensitive values
*   **Session Security:** NextAuth.js with secure JWT handling

### 11.3 Data Security

*   **Encryption at Rest:** Azure-managed encryption on storage and databases
*   **TLS 1.2+:** Enforced on all connections
*   **Blob Container Access:** Private containers with SAS tokens where needed
*   **Audit Logging:** Application Insights for access tracking

---

## 12. Environment Configuration

### 12.1 Key Environment Variables

| Category | Variable | Description |
|----------|----------|-------------|
| **OpenAI** | `OPENAI_ENDPOINT` | Azure OpenAI service endpoint |
| **OpenAI** | `OPENAI_API_VERSION` | API version string |
| **OpenAI** | `AZURE_OPENAI_API_KEY` | Service authentication key |
| **Auth** | `AUTH_MODE` | Authentication mode (sso/bypass) |
| **Auth** | `NEXTAUTH_SECRET` | Session encryption secret |
| **Analytics** | `PULSE_ANALYTICS_DB_HOST` | PostgreSQL hostname |
| **Storage** | `STORAGE_ACCOUNT_NAME` | Blob storage account |
| **Feature** | `NEXT_PUBLIC_ENABLE_ADMIN` | Admin UI visibility |
| **Feature** | `TRAINING_ORCHESTRATOR_ENABLED` | Trainer functionality |

### 12.2 Feature Flags

*   `NEXT_PUBLIC_ENABLE_ADMIN`: Show/hide admin navigation
*   `NEXT_PUBLIC_ENABLE_TRAINING`: Enable training mode UI
*   `NEXT_PUBLIC_ENV_NAME`: Environment indicator (dev/staging/prod)
*   `PULSE_TRAINER_ENABLED`: Enable trainer LLM calls
*   `TRAINING_ORCHESTRATOR_ENABLED`: Enable orchestrator features
*   `AUDIO_PROCESSING_ENABLED`: Enable audio pipeline

---

## Appendix: Architecture Diagram

For a visual representation of the complete system architecture, see the generated diagram:

*   **Source:** `docs/PULSE_network_diagram.py`
*   **Output:** `docs/PULSE_network_diagram.png` (PNG) or `docs/PULSE_network_diagram.svg` (SVG)
*   **Features:**
    - Terraform-parsed resource discovery
    - Azure CLI resource validation
    - A0 plotter-sized output with optimized layout
    - User interaction flows visualization

---

## Appendix: Security Assessment

For a comprehensive security assessment of the architecture, see:

*   **Document:** `docs/securedbydesign.md`
*   **Coverage:** Infrastructure, network, application, data, AI/ML security
*   **Status:** Secure-by-design analysis with production readiness checklist
