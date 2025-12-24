# PULSE Platform - Complete Rebuild Guide

This document contains everything needed to rebuild the PULSE platform from scratch.

## Quick Answer: YES, Everything Is In The Codebase

All AI Agents, Prompts, Personas, and configurations are **hardcoded as defaults** in the source code. localStorage is only used for user customizations that override defaults.

---

## Architecture Overview

```
pulseapp/
├── ui/                          # Next.js Frontend (deployed to Azure App Service)
├── orchestrator/                # Python Azure Functions (deployed to Function App)
├── main.tf, variables.tf, etc.  # Terraform IaC
├── docs/                        # Documentation
└── aidocs/                      # AI-specific documentation
```

---

## Critical Files & Their Contents

### 1. AI Components (All Defaults Hardcoded)

**File: `ui/app/admin/overview/page.tsx`**

Contains all default configurations:

| Component | Constant Name | Description |
|-----------|---------------|-------------|
| Personas | `DEFAULT_PERSONAS` | 4 customer types (Director, Relater, Socializer, Thinker) |
| Scoring Weights | `DEFAULT_SCORING_WEIGHTS` | BCE 40%, MCF 35%, CPO 25%, threshold 85% |
| Evaluator Criteria | `DEFAULT_EVALUATOR_CRITERIA` | Scoring criteria for BCE, MCF, CPO agents |
| Prompts | `DEFAULT_PROMPTS` | 6 system prompts including AI Feedback Agent |
| PULSE Stages | `DEFAULT_PULSE_STAGES` | 5 PULSE methodology stages with prompts |

### 2. System Prompts (in `DEFAULT_PROMPTS`)

1. **PULSE Customer Persona** - AI customer behavior in training
2. **PULSE Evaluator Orchestrator** - Session scoring orchestration
3. **PULSE Stage Detector** - Detects conversation stage (1-5)
4. **Misstep Detector** - Detects sales missteps
5. **Emotion Analyzer** - Customer emotion for avatar
6. **AI Feedback & Scoring Agent** - Comprehensive session analysis

### 3. Personas (in `DEFAULT_PERSONAS`)

| ID | Name | Difficulty | Voice | Description |
|----|------|------------|-------|-------------|
| director | Director | Expert/High Pressure | JennyNeural | Direct, results-oriented |
| relater | Relater | Beginner/Empathy | SaraNeural | Warm, relationship-focused |
| socializer | Socializer | Moderate/Enthusiasm | AriaNeural | Enthusiastic, talkative |
| thinker | Thinker | Challenging/Logic | MichelleNeural | Analytical, detail-oriented |

### 4. PULSE Stages (in `DEFAULT_PULSE_STAGES`)

1. **Probe** - Initial greeting, rapport, discovery
2. **Understand** - Deep dive into pain points
3. **Link** - Connect features to needs
4. **Solve** - Present solutions, handle objections
5. **Earn** - Close the sale

---

## Key UI Pages

| Route | File | Purpose |
|-------|------|---------|
| `/` | `ui/app/page.tsx` | Login (demo/demo) |
| `/pre-session` | `ui/app/pre-session/page.tsx` | Persona & scenario selection |
| `/session` | `ui/app/session/page.tsx` | Live training with avatar |
| `/feedback` | `ui/app/feedback/page.tsx` | AI-powered scoring & feedback |
| `/training` | `ui/app/training/page.tsx` | PULSE methodology training |
| `/admin` | `ui/app/admin/page.tsx` | Admin dashboard |
| `/admin/overview` | `ui/app/admin/overview/page.tsx` | AI Components management |
| `/admin/training` | `ui/app/admin/training/page.tsx` | Training administration |
| `/admin/auth` | `ui/app/admin/auth/page.tsx` | AuthN/Z management |

---

## Environment Variables

### UI (.env.local)
```bash
# Azure Function App URL
FUNCTION_APP_BASE_URL=https://func-pulse-training-scenario-prod.azurewebsites.net

# Azure Speech Services
AZURE_SPEECH_KEY=<your-key>
AZURE_SPEECH_REGION=eastus2

# Dev Mode
NEXT_PUBLIC_USE_DEV_SESSION=true
NEXT_PUBLIC_ENABLE_ADMIN=true
NEXT_PUBLIC_ENV_NAME=dev

# Optional
NEXT_PUBLIC_DEV_SESSION_ID=dev-test-session-001
```

### Orchestrator (Azure Function App Settings)
```bash
AZURE_OPENAI_ENDPOINT=https://<your-openai>.openai.azure.com/
AZURE_OPENAI_API_KEY=<your-key>
AZURE_STORAGE_CONNECTION_STRING=<your-connection-string>
ADMIN_EDIT_ENABLED=true
```

---

## Terraform Resources

All infrastructure is defined in Terraform. The following resources will be created:

### Core Infrastructure
| Resource | Name | Description |
|----------|------|-------------|
| Resource Group | `rg-PULSE-training-prod` | Contains all resources |
| Virtual Network | `vnet-PULSE-training-prod` | 10.10.0.0/16 |
| App Subnet | `PULSE-app-subnet` | 10.10.1.0/24, hosts App Service |
| Private Endpoints Subnet | `PULSE-private-endpoints-subnet` | 10.10.2.0/24 |
| Analytics Subnet | `PULSE-analytics-pg-subnet` | 10.10.3.0/24, hosts PostgreSQL |

### Compute
| Resource | Name | Description |
|----------|------|-------------|
| App Service Plan | `asp-PULSE-training-prod` | Linux, P1v3 (Premium) |
| Web App | `app-PULSE-training-ui-prod` | Next.js frontend |
| Function App | `func-PULSE-training-scenario-prod` | Python orchestrator |

### AI Services
| Resource | Name | Description |
|----------|------|-------------|
| Azure OpenAI Account | `cog-PULSE-training-prod` | Cognitive Services |
| Deployment: Persona-Core-Chat | gpt-5-chat | Main persona conversations (50K TPM) |
| Deployment: Persona-High-Reasoning | o4-mini | Evaluation/scoring (20K TPM) |
| Deployment: PULSE-Audio-Realtime | gpt-4o-realtime-preview | Real-time voice (4K TPM) |
| Deployment: PULSE-Whisper | whisper | Speech-to-text (1 capacity) |
| Deployment: Persona-Visual-Asset | sora-2 | **Disabled** (using Speech Avatar instead) |
| Azure Speech Account | `speech-pulse-training-prod` | Avatar service |

### Storage
| Resource | Name | Description |
|----------|------|-------------|
| Storage Account | `pulsetrainingprodsa123` | Blob storage |
| Container: certification-materials | | Training content |
| Container: interaction-logs | | Session logs |
| Container: prompts | | System prompts |

### Database
| Resource | Name | Description |
|----------|------|-------------|
| PostgreSQL Flexible Server | `pg-pulse-training-analytics-prod` | Analytics & readiness data |
| Database | `pulse_analytics` | Main database |

### Observability
| Resource | Name | Description |
|----------|------|-------------|
| Log Analytics Workspace | `law-PULSE-training-prod` | Centralized logging |
| Application Insights | `appi-PULSE-training-prod` | APM & telemetry |

### Private Networking
| Resource | Purpose |
|----------|---------|
| Private Endpoint: OpenAI | Secure access to Azure OpenAI |
| Private Endpoint: Storage Blob | Secure access to storage |
| Private Endpoint: Speech | Secure access to Speech Services |
| Private Endpoint: Web App | Optional, for private access |
| DNS Zone: privatelink.openai.azure.com | OpenAI name resolution |
| DNS Zone: privatelink.blob.core.windows.net | Blob name resolution |
| DNS Zone: privatelink.cognitiveservices.azure.com | Speech name resolution |
| DNS Zone: privatelink.azurewebsites.net | Web App name resolution |
| DNS Zone: privatelink.postgres.database.azure.com | PostgreSQL name resolution |

### Deploy Infrastructure
```bash
terraform init
terraform plan -var-file=prod.tfvars
terraform apply -var-file=prod.tfvars
```

### Import Existing Resources (if recreating state)
If you need to import existing Azure resources into a fresh Terraform state:
```bash
# Import PULSE-Whisper deployment (if it exists but wasn't in Terraform)
terraform import 'module.openai.azurerm_cognitive_deployment.PULSE_whisper' \
  '/subscriptions/<sub-id>/resourceGroups/rg-PULSE-training-prod/providers/Microsoft.CognitiveServices/accounts/cog-PULSE-training-prod/deployments/PULSE-Whisper'

# Import prompts container (if it exists but wasn't in Terraform)
terraform import 'azurerm_storage_container.prompts' \
  'https://pulsetrainingprodsa123.blob.core.windows.net/prompts'
```

---

## Deployment Commands

### Build & Deploy UI
```bash
cd ui
npm install
npm run build

# Package standalone
cp -r .next/static .next/standalone/.next/
mkdir -p .next/standalone/public
cp public/intro.mp4 .next/standalone/public/
cd .next/standalone && zip -r ../../ui-standalone.zip .

# Deploy to Azure
curl -X POST "https://app-pulse-training-ui-prod.scm.azurewebsites.net/api/zipdeploy" \
  -u '$app-PULSE-training-ui-prod:<password>' \
  --data-binary @ui-standalone.zip \
  -H "Content-Type: application/zip"

az webapp restart --resource-group "rg-PULSE-training-prod" --name "app-PULSE-training-ui-prod"
```

### Deploy Orchestrator (Python Functions)
```bash
cd orchestrator
zip -r ../orchestrator.zip . -x "*.pyc" -x "__pycache__/*" -x ".python_packages/*"

az functionapp deployment source config-zip \
  --resource-group "rg-PULSE-training-prod" \
  --name "func-pulse-training-scenario-prod" \
  --src orchestrator.zip \
  --build-remote true
```

---

## localStorage Keys (User Customizations Only)

These are for user overrides of defaults - NOT required for rebuild:

| Key | Purpose | Default Source |
|-----|---------|----------------|
| `pulse_personas` | Persona customizations | `DEFAULT_PERSONAS` |
| `pulse_prompts` | Prompt customizations | `DEFAULT_PROMPTS` |
| `pulse_stages` | Stage customizations | `DEFAULT_PULSE_STAGES` |
| `pulse_agent_config` | Scoring weight overrides | `DEFAULT_SCORING_WEIGHTS` |
| `pulse_auth` | Login session | N/A (demo/demo) |
| `pulse_session_id` | Current session ID | Auto-generated |
| `pulse_user_session_history_<user>` | User's session history | Empty on fresh start |

---

## Files to Backup (Beyond Git)

1. **Azure credentials** - Not in repo (use Azure Key Vault or secure storage)
2. **`.env` / `.env.local`** - Contains secrets
3. **`prod.tfvars`** - Contains sensitive Terraform variables
4. **Terraform state** - `terraform.tfstate` (use remote backend in production)

---

## Verification Checklist

After rebuild, verify:

- [ ] Login works (demo/demo)
- [ ] Pre-session shows 4 personas
- [ ] Session page loads avatar
- [ ] Speech recognition works
- [ ] AI responds with persona voice
- [ ] Feedback page shows AI analysis
- [ ] Admin > AI Components shows all tabs
- [ ] Admin > Training shows modules
- [ ] Admin > Auth shows user management

---

## Summary

**Everything needed to rebuild is in the Git repository:**

✅ All AI prompts hardcoded in `DEFAULT_PROMPTS`  
✅ All personas hardcoded in `DEFAULT_PERSONAS`  
✅ All PULSE stages hardcoded in `DEFAULT_PULSE_STAGES`  
✅ All scoring weights hardcoded in `DEFAULT_SCORING_WEIGHTS`  
✅ All evaluator criteria hardcoded in `DEFAULT_EVALUATOR_CRITERIA`  
✅ Infrastructure as Code in Terraform files  
✅ Deployment scripts documented  

**Only things NOT in repo (by design):**
- Azure credentials/secrets
- User session history (localStorage, ephemeral)
- Terraform state (should use remote backend)
