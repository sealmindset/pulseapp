# Azure AI Models & Requirements - PULSE Training Platform

**Last Updated:** 2025-12-21  
**Environment:** Production (East US 2)  
**Document Purpose:** Complete inventory of AI models, services, and configurations used in the PULSE sales training platform.

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Azure OpenAI Models](#azure-openai-models)
3. [Azure Speech Services](#azure-speech-services)
4. [Model Configuration Matrix](#model-configuration-matrix)
5. [Capacity & Quota Planning](#capacity--quota-planning)
6. [Environment Variables](#environment-variables)
7. [Code References](#code-references)
8. [Architecture Decision Records](#architecture-decision-records)

---

## Executive Summary

The PULSE training platform leverages **7 AI models/services** across Azure OpenAI and Azure Cognitive Services to deliver an interactive, AI-driven sales training experience:

- **3 Active Azure OpenAI Deployments** (gpt-5-chat, o4-mini, gpt-4o-realtime-preview)
- **1 Disabled Azure OpenAI Deployment** (sora-2)
- **2 Azure Speech Services** (Avatar TTS, Speech-to-Text)
- **1 Fallback Service** (Whisper for transcription)

**Total Production Capacity:** 74K TPM (Tokens Per Minute) across OpenAI deployments  
**Monthly Cost Estimate:** ~$500-1,500 depending on usage patterns

---

## Azure OpenAI Models

### 1. Persona-Core-Chat (`gpt-5-chat`)

**Azure OpenAI Deployment Name:** `Persona-Core-Chat`

#### Model Details
- **Model ID:** `gpt-5-chat`
- **Version:** `2025-10-03`
- **SKU:** GlobalStandard
- **Capacity:** 50K TPM (Production)
- **Status:** ✅ **Active**

#### Primary Use Cases
1. **AI Customer Personas** - Powers all four behavioral persona types:
   - **Director:** Direct, results-oriented, impatient
   - **Relater:** Warm, relationship-focused, patient
   - **Socializer:** Enthusiastic, talkative, optimistic
   - **Thinker:** Analytical, detail-oriented, cautious

2. **Conversational AI** - Real-time dialogue generation during training sessions
3. **Response Generation** - Context-aware replies based on PULSE methodology
4. **Session Interactions** - Maintains conversation flow and persona consistency

#### Technical Implementation
- **Service:** [`openai_client.py`](../orchestrator/shared_code/openai_client.py)
- **Function:** `chat_completion(deployment_key="deployment_core_chat")`
- **Temperature:** 0.7-0.8 (allows natural variation)
- **Max Tokens:** 200 (conversational responses)

#### Configuration
```python
# Environment Variable
OPENAI_DEPLOYMENT_PERSONA_CORE_CHAT=Persona-Core-Chat

# Terraform Variable
openai_model_core_chat_id      = "gpt-5-chat"
openai_model_core_chat_version = "2025-10-03"
openai_deployment_core_chat_capacity = 50  # 50K TPM
```

---

### 2. Persona-High-Reasoning (`o4-mini`)

**Azure OpenAI Deployment Name:** `Persona-High-Reasoning`

#### Model Details
- **Model ID:** `o4-mini`
- **Version:** `2025-04-16`
- **SKU:** GlobalStandard
- **Capacity:** 20K TPM (Production)
- **Status:** ✅ **Active**

#### Primary Use Cases
1. **PULSE Evaluation (0-3 Scale)**
   - Analyzes complete training session transcripts
   - Scores performance across PULSE methodology steps
   - Generates detailed feedback and improvement recommendations

2. **BCE/MCF/CPO Assessment**
   - **BCE (Behavioral Certification Exam):** Evaluates behavioral mastery
   - **MCF (Methodology Fidelity):** Assesses PULSE framework adherence
   - **CPO (Conversion & Psychological Outcome):** Measures psychological lever deployment

3. **Adaptive Training Logic**
   - Generates follow-up questions based on learner performance
   - Estimates mastery levels (weak, developing, solid, mastery_likely)
   - Provides diagnostic insights and error pattern analysis

4. **Self-Annealing System**
   - Emits trainer change logs when patterns are detected
   - Suggests rubric, prompt, and scenario improvements

#### Technical Implementation
- **Services:**
  - [`feedback_session/__init__.py`](../orchestrator/feedback_session/__init__.py) - Session evaluation
  - [`trainer_pulse_step/__init__.py`](../orchestrator/trainer_pulse_step/__init__.py) - Adaptive training
- **Function:** `_call_openai_trainer()`, `_call_openai_pulse_evaluator()`
- **Temperature:** 0.2 (consistent, analytical evaluation)
- **Response Format:** JSON object (structured evaluation data)

#### Configuration
```python
# Environment Variable
OPENAI_DEPLOYMENT_PERSONA_HIGH_REASONING=Persona-High-Reasoning

# Terraform Variable
openai_model_high_reasoning_id      = "o4-mini"
openai_model_high_reasoning_version = "2025-04-16"
openai_deployment_high_reasoning_capacity = 20  # 20K TPM
```

---

### 3. PULSE-Audio-Realtime (`gpt-4o-realtime-preview`)

**Azure OpenAI Deployment Name:** `PULSE-Audio-Realtime`

#### Model Details
- **Model ID:** `gpt-4o-realtime-preview`
- **Version:** `2024-12-17`
- **SKU:** GlobalStandard
- **Capacity:** 4K TPM (Production)
- **Quota Limit:** 6K TPM (Azure subscription limit)
- **Status:** ✅ **Active**

#### Primary Use Cases
1. **Text-to-Speech (TTS)** - Generates natural-sounding speech from AI persona responses
2. **Voice Synthesis** - Creates audio for real-time voice training sessions
3. **Audio Output** - Powers the AI customer's voice during interactive scenarios

#### Technical Implementation
- **Service:** [`openai_client.py`](../orchestrator/shared_code/openai_client.py)
- **Function:** `generate_speech(voice, speed)`
- **Supported Voices:** alloy, echo, fable, onyx, nova, shimmer
- **Output Format:** MP3
- **Speed Range:** 0.25 to 4.0

#### Configuration
```python
# Environment Variable
OPENAI_DEPLOYMENT_PULSE_AUDIO_REALTIME=PULSE-Audio-Realtime

# Terraform Variable
openai_model_audio_realtime_id      = "gpt-4o-realtime-preview"
openai_model_audio_realtime_version = "2024-12-17"
openai_deployment_audio_realtime_capacity = 4  # 4K TPM
```

#### Important Notes
⚠️ **Quota Constraint:** Current usage is 4K TPM out of 6K TPM subscription limit. Monitor usage closely during high-volume training sessions (e.g., executive demos with 30-minute live voice interactions).

---

### 4. Persona-Visual-Asset (`sora-2`) - DISABLED

**Azure OpenAI Deployment Name:** `Persona-Visual-Asset`

#### Model Details
- **Model ID:** `sora-2`
- **Version:** (not specified)
- **SKU:** GlobalStandard
- **Capacity:** 2K TPM (if enabled)
- **Status:** ❌ **DISABLED**

#### Reason for Disabling
Sora-2 has been **replaced by Azure Speech Services Avatar** due to the following limitations:
- **12-second video limit** - Insufficient for realistic training conversations
- **No real-time streaming** - Cannot support interactive back-and-forth dialogue
- **Higher latency** - Not suitable for conversational AI

#### Configuration
```python
# Terraform Variable
enable_visual_asset_deployment = false  # Disabled in prod
```

#### Migration Path
All avatar functionality has been migrated to **Azure Speech Services Avatar** (see below), which provides:
- ✅ Unlimited duration (no 12-second limit)
- ✅ Real-time WebRTC streaming
- ✅ Pre-built avatar characters with lip-sync
- ✅ Lower latency for conversational AI

---

## Azure Speech Services

### 5. Azure Speech Avatar - Text-to-Speech

**Service:** Azure Cognitive Services - Speech Avatar  
**Region:** East US 2

#### Service Details
- **Technology:** Real-time WebRTC streaming
- **Avatar Character:** `lisa` (female avatar)
- **Style:** `casual-sitting`
- **Status:** ✅ **Active**

#### Persona-Specific Voice Mapping

| Persona | Voice | Voice Style | Characteristics |
|---------|-------|-------------|----------------|
| **Director** | `en-US-JennyNeural` | `customerservice` | Confident, professional, direct |
| **Relater** | `en-US-SaraNeural` | `friendly` | Warm, empathetic, patient |
| **Socializer** | `en-US-AriaNeural` | `cheerful` | Energetic, enthusiastic, expressive |
| **Thinker** | `en-US-MichelleNeural` | `calm` | Analytical, measured, thoughtful |

#### Emotional Expression Support
The avatar supports dynamic emotional states through SSML (Speech Synthesis Markup Language):
- `neutral` → neutral style
- `interested` → friendly style
- `skeptical` → unfriendly style
- `pleased` → cheerful style
- `concerned` → empathetic style
- `excited` → excited style
- `hesitant` → shy style

#### Technical Implementation
- **Service:** [`avatar_service.py`](../orchestrator/shared_code/avatar_service.py)
- **Functions:**
  - `generate_avatar_video()` - Creates SSML configuration
  - `get_avatar_token()` - Authentication for client-side SDK
  - `get_ice_server_info()` - WebRTC connection setup
- **Client Integration:** WebRTC streaming to browser (Speech SDK)

#### Configuration
```python
# Environment Variables
AZURE_SPEECH_KEY=<api-key>
AZURE_SPEECH_REGION=eastus2
```

#### Advantages Over Sora-2
1. **No Time Limit** - Supports unlimited conversation duration
2. **Real-Time Streaming** - Low latency for interactive dialogue
3. **Lip-Sync Accuracy** - Built-in synchronization with speech
4. **Cost Effective** - Pay-per-use model vs. pre-generated videos

---

### 6. Azure Speech Services - Speech-to-Text (STT)

**Service:** Azure Cognitive Services - Speech Recognition  
**Region:** East US 2

#### Service Details
- **Technology:** Real-time speech recognition
- **Language:** en-US (configurable)
- **Format Support:** webm, wav, mp3, ogg, flac
- **Status:** ✅ **Active** (Primary STT)

#### Primary Use Cases
1. **Trainee Speech Transcription** - Converts trainee audio responses to text
2. **High Rate Limits** - Better throughput than OpenAI Whisper
3. **Production STT** - Primary transcription service for live training

#### Technical Implementation
- **Service:** [`avatar_service.py`](../orchestrator/shared_code/avatar_service.py)
- **Function:** `transcribe_audio_speech_services()`
- **Response Format:** Detailed JSON with confidence scores
- **Timeout:** 30 seconds

#### Configuration
```python
# Environment Variables
AZURE_SPEECH_KEY=<api-key>
AZURE_SPEECH_REGION=eastus2
```

#### Fallback Strategy
If Azure Speech STT fails or is unavailable, the system automatically falls back to **Azure OpenAI Whisper** (see below).

---

### 7. Azure OpenAI Whisper (Fallback STT)

**Azure OpenAI Deployment Name:** `PULSE-Whisper` (default)

#### Model Details
- **Model:** Whisper
- **Version:** Not specified in terraform (managed deployment)
- **Status:** ✅ **Available** (Fallback only)

#### Primary Use Cases
1. **Backup Transcription** - Alternative when Azure Speech Services unavailable
2. **Development/Testing** - Used in environments without Speech Services configured

#### Technical Implementation
- **Service:** [`openai_client.py`](../orchestrator/shared_code/openai_client.py)
- **Function:** `transcribe_audio()`
- **Environment Variable:** `OPENAI_DEPLOYMENT_WHISPER` (defaults to `PULSE-Whisper`)

#### Configuration
```python
# Environment Variable (optional override)
OPENAI_DEPLOYMENT_WHISPER=PULSE-Whisper
```

---

## Model Configuration Matrix

| Deployment Name | Model | Version | Capacity (TPM) | Primary Purpose | Status |
|----------------|-------|---------|----------------|----------------|--------|
| **Persona-Core-Chat** | gpt-5-chat | 2025-10-03 | 50,000 | Conversational AI, Personas | ✅ Active |
| **Persona-High-Reasoning** | o4-mini | 2025-04-16 | 20,000 | Evaluation, Adaptive Training | ✅ Active |
| **PULSE-Audio-Realtime** | gpt-4o-realtime-preview | 2024-12-17 | 4,000 | Text-to-Speech | ✅ Active |
| **Persona-Visual-Asset** | sora-2 | - | 2,000 | Video Generation | ❌ Disabled |
| **Azure Speech Avatar** | (Service) | - | N/A | Real-time Avatar Streaming | ✅ Active |
| **Azure Speech STT** | (Service) | - | N/A | Primary Audio Transcription | ✅ Active |
| **PULSE-Whisper** | whisper | - | N/A | Fallback Audio Transcription | ✅ Available |

**Total Active TPM:** 74,000 (50K + 20K + 4K)

---

## Capacity & Quota Planning

### Current Production Allocation

```
Azure OpenAI Total: 74K TPM
├── Persona-Core-Chat:       50K TPM (67.6%)
├── Persona-High-Reasoning:  20K TPM (27.0%)
└── PULSE-Audio-Realtime:     4K TPM (5.4%)
```

### Quota Constraints

⚠️ **Audio Realtime Quota Limit:**
- **Subscription Limit:** 6K TPM
- **Current Usage:** 4K TPM
- **Remaining Headroom:** 2K TPM (33%)
- **Recommendation:** Monitor usage during executive demos and large training sessions

### Scaling Considerations

**If you need to scale up:**

1. **Persona-Core-Chat** (50K → 100K TPM)
   - Supports 2x concurrent training sessions
   - Estimated cost increase: +$300/month

2. **Persona-High-Reasoning** (20K → 40K TPM)
   - Supports real-time evaluation during sessions
   - Estimated cost increase: +$200/month

3. **PULSE-Audio-Realtime** (4K → 6K TPM - **MAX**)
   - Requires quota increase request to Microsoft
   - Current limit is subscription-level constraint

### Usage Patterns

**Typical Training Session:**
- **Core Chat:** ~5K tokens per session (persona dialogue)
- **High Reasoning:** ~10K tokens per session (evaluation)
- **Audio Realtime:** ~2K tokens per session (TTS generation)

**Concurrent Session Capacity:**
- **Current:** ~8-10 concurrent sessions
- **With scaling:** 15-20 concurrent sessions

---

## Environment Variables

> **⚠️ IMPORTANT: When Deployed in Azure**  
> Most environment variables listed below are **automatically configured** by Terraform when deploying to Azure App Service and Function App. You do **NOT** need to manually set these variables in the Azure Portal when using the terraform deployment.
> 
> **Terraform Configuration File:** [`modules/app/main.tf`](../modules/app/main.tf)

---

### 🤖 Auto-Configured Variables (Terraform-Managed)

These variables are **automatically injected** by Terraform from Azure resource outputs. **Do NOT manually configure these in Azure Portal** when using terraform deployment.

#### Azure OpenAI Configuration

```bash
# ✅ AUTO-CONFIGURED by Terraform
OPENAI_ENDPOINT=https://cog-pulse-training-prod.openai.azure.com/
OPENAI_API_VERSION=2024-12-01-preview
AZURE_OPENAI_API_KEY=<api-key>

# ✅ AUTO-CONFIGURED - Deployment Names
OPENAI_DEPLOYMENT_PERSONA_CORE_CHAT=Persona-Core-Chat
OPENAI_DEPLOYMENT_PERSONA_HIGH_REASONING=Persona-High-Reasoning
OPENAI_DEPLOYMENT_PULSE_AUDIO_REALTIME=PULSE-Audio-Realtime
OPENAI_DEPLOYMENT_PERSONA_VISUAL_ASSET=Persona-Visual-Asset  # Not used
```

**Terraform Source:**
- `OPENAI_ENDPOINT` → `module.openai.endpoint`
- `AZURE_OPENAI_API_KEY` → `module.openai.primary_key`
- `OPENAI_API_VERSION` → `var.openai_api_version`
- Deployment names → `module.openai.deployment_*_name`

---

#### Azure Speech Services Configuration

```bash
# ✅ AUTO-CONFIGURED by Terraform
AZURE_SPEECH_KEY=<api-key>
AZURE_SPEECH_REGION=eastus2
```

**Terraform Source:**
- `AZURE_SPEECH_KEY` → `module.speech.speech_key`
- `AZURE_SPEECH_REGION` → `module.speech.speech_region`

---

#### Storage Configuration

```bash
# ✅ AUTO-CONFIGURED by Terraform
STORAGE_ACCOUNT_NAME=pulsetrainingprodsa123
STORAGE_CERTIFICATION_CONTAINER=certification-materials
STORAGE_INTERACTION_LOGS_CONTAINER=interaction-logs
AzureWebJobsStorage=<connection-string>  # Function App only
```

**Terraform Source:**
- `STORAGE_ACCOUNT_NAME` → `azurerm_storage_account.storage.name`
- Container names → `azurerm_storage_container.*.name`
- `AzureWebJobsStorage` → `storage_account_primary_connection_string`

---

#### Analytics Database Configuration

```bash
# ✅ AUTO-CONFIGURED by Terraform
PULSE_ANALYTICS_DB_HOST=<postgres-fqdn>
PULSE_ANALYTICS_DB_PORT=5432
PULSE_ANALYTICS_DB_NAME=pulse_analytics
PULSE_ANALYTICS_DB_USER=pulse_analytics_admin
PULSE_ANALYTICS_DB_PASSWORD=<password>  # From terraform variables
```

**Terraform Source:**
- `PULSE_ANALYTICS_DB_HOST` → `module.analytics_postgres.analytics_pg_fqdn`
- `PULSE_ANALYTICS_DB_NAME` → `module.analytics_postgres.analytics_pg_database_name`
- `PULSE_ANALYTICS_DB_USER` → `var.analytics_pg_admin_username`
- `PULSE_ANALYTICS_DB_PASSWORD` → `var.analytics_pg_admin_password`

---

#### Application Insights

```bash
# ✅ AUTO-CONFIGURED by Terraform
APPLICATIONINSIGHTS_CONNECTION_STRING=<connection-string>
```

**Terraform Source:**
- `APPLICATIONINSIGHTS_CONNECTION_STRING` → `azurerm_application_insights.app_insights.connection_string`

---

#### Other Auto-Configured Variables

```bash
# ✅ AUTO-CONFIGURED by Terraform
BEHAVIORAL_MASTERY_THRESHOLD=0.9
TRAINING_ORCHESTRATOR_ENABLED=true  # Auto-enabled in production
AUDIO_PROCESSING_ENABLED=true       # Auto-enabled in production
FUNCTIONS_WORKER_RUNTIME=python    # Function App only
WEBSITE_RUN_FROM_PACKAGE=0         # Web App only
FUNCTION_APP_BASE_URL=https://func-pulse-training-scenario-prod.azurewebsites.net/api
```

---

### 🔧 Manually-Configured Variables (Feature Flags & Optional)

These variables are **NOT** automatically configured by Terraform and must be manually set in Azure Portal (App Service Configuration) if you wish to enable/disable specific features.

#### Optional Feature Flags

```bash
# ⚠️ MANUAL CONFIGURATION - Set in Azure Portal if needed
PULSE_TRAINER_ENABLED=true          # Adaptive AI trainer (default: not set, disabled)
PULSE_EVALUATOR_ENABLED=true        # Session evaluation (default: not set, disabled)
PULSE_ANALYTICS_ENABLED=true        # Longitudinal analytics (default: not set, disabled)
```

**Current Status:**
- `TRAINING_ORCHESTRATOR_ENABLED` → ✅ Auto-enabled by Terraform
- `PULSE_TRAINER_ENABLED` → ⚠️ Must be manually set to `true` to enable
- `PULSE_EVALUATOR_ENABLED` → ⚠️ Must be manually set to `true` to enable
- `PULSE_ANALYTICS_ENABLED` → ⚠️ Must be manually set to `true` to enable

---

#### Optional Overrides (Advanced)

```bash
# ⚠️ MANUAL CONFIGURATION - Only set if you need to override defaults
OPENAI_DEPLOYMENT_WHISPER=PULSE-Whisper      # Default fallback STT deployment
AZURE_SPEECH_ENDPOINT=<custom-endpoint>      # Custom Speech Services endpoint
PULSE_EVALUATOR_PROMPT_ID=pulse-evaluator-v1 # Custom evaluator prompt ID
PROMPTS_CONTAINER=interaction-logs           # Already set by Terraform
```

---

### 📝 Environment Variable Summary

| Variable | Auto-Configured? | Where to Set | Notes |
|----------|-----------------|--------------|-------|
| `OPENAI_ENDPOINT` | ✅ Yes | Terraform | From Azure OpenAI resource |
| `AZURE_OPENAI_API_KEY` | ✅ Yes | Terraform | From Azure OpenAI primary key |
| `OPENAI_DEPLOYMENT_*` | ✅ Yes | Terraform | From deployment names |
| `AZURE_SPEECH_KEY` | ✅ Yes | Terraform | From Speech Services |
| `AZURE_SPEECH_REGION` | ✅ Yes | Terraform | From resource location |
| `STORAGE_ACCOUNT_NAME` | ✅ Yes | Terraform | From storage resource |
| `PULSE_ANALYTICS_DB_*` | ✅ Yes | Terraform | From PostgreSQL resource |
| `TRAINING_ORCHESTRATOR_ENABLED` | ✅ Yes | Terraform | Set to `true` in prod |
| `PULSE_TRAINER_ENABLED` | ❌ No | Azure Portal | Feature flag (optional) |
| `PULSE_EVALUATOR_ENABLED` | ❌ No | Azure Portal | Feature flag (optional) |
| `PULSE_ANALYTICS_ENABLED` | ❌ No | Azure Portal | Feature flag (optional) |
| `OPENAI_DEPLOYMENT_WHISPER` | ❌ No | Azure Portal | Optional override |

---

### 🚀 Quick Setup Guide

#### For Azure Deployment (Using Terraform):
1. **Run Terraform:** `terraform apply -var-file=prod.tfvars`
2. **All required variables are auto-configured** ✅
3. **Optionally enable features** in Azure Portal:
   - Navigate to: Azure Portal → Function App → Configuration → Application Settings
   - Add: `PULSE_TRAINER_ENABLED=true`
   - Add: `PULSE_EVALUATOR_ENABLED=true`
   - Add: `PULSE_ANALYTICS_ENABLED=true`
   - Click **Save** and restart the Function App

#### For Local Development:
You must manually set all variables in your local `.env` file or environment:

```bash
# Create .env file in orchestrator/ directory
cp .env.example .env

# Set all required variables
OPENAI_ENDPOINT=https://cog-pulse-training-prod.openai.azure.com/
AZURE_OPENAI_API_KEY=<your-key>
AZURE_SPEECH_KEY=<your-key>
# ... etc
```

---

## Code References

### Shared Services

#### OpenAI Client
**File:** [`orchestrator/shared_code/openai_client.py`](../orchestrator/shared_code/openai_client.py)

**Functions:**
- `chat_completion()` - Chat completions (Persona-Core-Chat, High-Reasoning)
- `extract_chat_content()` - Parse OpenAI responses
- `transcribe_audio()` - Whisper STT (fallback)
- `generate_speech()` - TTS (Audio-Realtime)
- `generate_conversation_response()` - Persona-aware dialogue

#### Avatar Service
**File:** [`orchestrator/shared_code/avatar_service.py`](../orchestrator/shared_code/avatar_service.py)

**Functions:**
- `generate_avatar_video()` - SSML configuration for avatar
- `get_avatar_config()` - Persona-specific avatar settings
- `get_avatar_token()` - Authentication for Speech SDK
- `transcribe_audio_speech_services()` - Primary STT
- `_build_avatar_ssml()` - SSML markup generation

### Function Endpoints

#### Feedback Session (Evaluation)
**File:** [`orchestrator/feedback_session/__init__.py`](../orchestrator/feedback_session/__init__.py)

**AI Usage:**
- Uses **Persona-High-Reasoning** for session evaluation
- Calls `_call_openai_pulse_evaluator()` for BCE/MCF/CPO scoring
- Temperature: 0.2 (consistent evaluation)

#### Trainer PULSE Step (Adaptive Training)
**File:** [`orchestrator/trainer_pulse_step/__init__.py`](../orchestrator/trainer_pulse_step/__init__.py)

**AI Usage:**
- Uses **Persona-High-Reasoning** for adaptive training
- Calls `_call_openai_trainer()` for follow-up questions
- Generates mastery estimates and diagnostic insights

#### Chat Endpoint
**File:** [`orchestrator/chat/__init__.py`](../orchestrator/chat/__init__.py)

**AI Usage:**
- Uses **Persona-Core-Chat** for conversational AI
- Real-time persona dialogue generation
- Maintains conversation context

#### Audio Chunk (Real-time Audio)
**File:** [`orchestrator/audio_chunk/__init__.py`](../orchestrator/audio_chunk/__init__.py)

**AI Usage:**
- Uses **Azure Speech STT** (primary) or **Whisper** (fallback) for transcription
- Uses **gpt-5-chat** for AI response generation
- Uses **Audio-Realtime** or **Speech Avatar** for TTS

---

## Architecture Decision Records

### ADR-001: Sora-2 Deprecation in Favor of Azure Speech Avatar

**Date:** 2025-12-19  
**Status:** ✅ Implemented

**Context:**
Initial design included Sora-2 for avatar video generation, but the 12-second video limit proved impractical for realistic training conversations.

**Decision:**
Migrate to Azure Speech Services Avatar, which provides:
- Real-time WebRTC streaming (unlimited duration)
- Built-in lip-sync with TTS
- Lower latency for conversational AI
- Pre-built avatar characters

**Consequences:**
- **Positive:** Unlimited conversation duration, real-time interactivity
- **Positive:** Reduced latency and better user experience
- **Negative:** Less customizable avatar appearance (limited to Azure Speech characters)
- **Migration:** Set `enable_visual_asset_deployment = false` in terraform

---

### ADR-002: Dual STT Strategy (Speech Services + Whisper)

**Date:** 2025-12-18  
**Status:** ✅ Implemented

**Context:**
Need reliable speech-to-text with high rate limits for production, but also need fallback for development/testing.

**Decision:**
Use Azure Speech Services as primary STT with OpenAI Whisper as fallback:
1. Try Azure Speech STT first (higher rate limits)
2. Fall back to Whisper if Speech Services unavailable

**Consequences:**
- **Positive:** Higher reliability and throughput
- **Positive:** Better dev/test experience without Speech Services setup
- **Negative:** Slightly more complex error handling

---

### ADR-003: High Reasoning Model for Evaluation

**Date:** 2025-11-30  
**Status:** ✅ Implemented

**Context:**
Session evaluation (BCE/MCF/CPO) and adaptive training require complex reasoning about learner performance.

**Decision:**
Use o4-mini (Persona-High-Reasoning) for all evaluation and adaptive training logic, not the core chat model.

**Consequences:**
- **Positive:** Better evaluation quality and consistency
- **Positive:** Separation of concerns (conversation vs. evaluation)
- **Negative:** Additional model deployment and cost
- **Mitigation:** Lower temperature (0.2) for cost-effective, consistent evaluations

---

## Maintenance & Monitoring

### Model Version Updates

**Recommended Schedule:**
- **Monthly:** Review Azure OpenAI model version updates
- **Quarterly:** Evaluate new model capabilities
- **Annually:** Major version upgrades (e.g., gpt-5 → gpt-6)

**Update Process:**
1. Test new version in staging environment
2. Update `variables.tf` with new version
3. Run `terraform plan` to preview changes
4. Apply during maintenance window
5. Monitor performance and costs

### Cost Tracking

**Monitoring Points:**
- Azure OpenAI API usage (tokens per deployment)
- Azure Speech Services usage (characters synthesized, audio minutes)
- Deployment capacity utilization (% of TPM used)

**Budget Alerts:**
Set up Azure Cost Management alerts for:
- Daily spend > $50
- Monthly projected > $2,000
- Unexpected TPM increases

---

## Support & Troubleshooting

### Common Issues

#### Issue 1: "Missing Azure OpenAI configuration"
**Error:** `RuntimeError: Missing AZURE_OPENAI_API_KEY`

**Solution:**
1. Verify environment variables in Azure App Service Configuration
2. Check Key Vault references (if using)
3. Restart App Service after configuration changes

#### Issue 2: Quota Exceeded on Audio Realtime
**Error:** HTTP 429 - Rate limit exceeded

**Solution:**
1. Current limit: 6K TPM subscription-wide
2. Request quota increase via Azure Support
3. Implement retry logic with exponential backoff

#### Issue 3: Avatar Not Streaming
**Error:** WebRTC connection failure

**Solution:**
1. Verify `AZURE_SPEECH_KEY` and `AZURE_SPEECH_REGION`
2. Check firewall allows WebRTC connections
3. Validate ICE server configuration in browser console

---

## Contacts & Resources

### Internal Team
- **AI/ML Lead:** Sales Excellence Team
- **Infrastructure:** Azure Operations
- **Security:** InfoSec Team

### Azure Resources
- **Azure OpenAI Documentation:** https://learn.microsoft.com/azure/ai-services/openai/
- **Azure Speech Avatar Guide:** https://learn.microsoft.com/azure/ai-services/speech-service/text-to-speech-avatar/
- **Quota Management:** Azure Portal → Quotas

### Emergency Contacts
- **Azure Support:** Portal support ticket
- **On-Call:** (see team wiki)

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-12-21 | AI Analysis | Initial documentation of AI models and requirements |
| 1.1 | 2025-12-21 | AI Analysis | Clarified auto-configured vs. manually-configured environment variables for Azure deployment |

---

**End of Document**
