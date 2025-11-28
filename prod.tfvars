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

# Web App private endpoint stays enabled for prod
enable_webapp_private_endpoint = true

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