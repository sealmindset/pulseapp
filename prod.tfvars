# Azure subscription
subscription_id = "f1e6d3a4-b486-4abc-8352-2f8f540540b4"

# Core environment
environment         = "prod"
location            = "East US 2"
resource_group_name = "rg-PULSE-training-prod"
project_name        = "PULSE-training"

# Tagging / ownership
owner = "Sales Excellence"

# Storage (must be globally unique, 3-24 chars, lowercase letters/numbers only)
storage_account_name = "pulsetrainingprodsa123"

# Behavioral mastery threshold used by the trainer/evaluator (0.85–1.0)
behavioral_mastery_threshold = 0.9

# App Service SKU - P1v3 (Premium V3) for production with VNet integration
app_service_sku_name = "P1v3"

# Web App private endpoint stays enabled for prod
enable_webapp_private_endpoint = true

# Quotas approved 2025-12-19
# App Service (Web + Function) - approved and enabled
enable_app_service             = true

# Visual asset deployment disabled - using Azure Speech Avatar instead of Sora-2
# Sora-2 has 12-second limit; Speech Avatar provides unlimited real-time streaming
enable_visual_asset_deployment = false

# Azure Speech Avatar - real-time lip-synced avatar via WebRTC
enable_speech_avatar = true

# Analytics PostgreSQL (Longitudinal Store + Readiness DB)
# Sizing here assumes an early pilot: General Purpose D2s v3 + 32 GB storage.
# You can scale up sku/storage later via Terraform if needed.
analytics_pg_subnet_prefix         = "10.10.3.0/24"
analytics_pg_version               = "16"
analytics_pg_sku_name              = "GP_Standard_D2s_v3"
analytics_pg_storage_mb            = 32768
analytics_pg_backup_retention_days = 7

# IMPORTANT: Do NOT commit real passwords; keep this file local or use a secure
# tfvars mechanism in CI. Replace the value below locally before running plan/apply.
analytics_pg_admin_username = "pulse_analytics_admin"
analytics_pg_admin_password = "CHANGE_ME_STRONG_SECRET"

# TEMPORARY: Enable public network access for persona integration testing
# Set back to false after testing is complete!
openai_public_network_access_enabled = true

# OpenAI deployment capacity (in thousands of TPM)
# Increased for executive demo - 30 min live voice interaction requires headroom
# Original values: core_chat=5, high_reasoning=3, audio_realtime=2
openai_deployment_core_chat_capacity      = 50   # Main persona conversations
openai_deployment_high_reasoning_capacity = 20   # Evaluation/scoring
openai_deployment_audio_realtime_capacity = 4    # Real-time voice STT/TTS (quota limit: 6, current usage: 2)