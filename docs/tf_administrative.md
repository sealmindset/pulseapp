# PULSE Platform: Terraform Administrative Guide

> **Last Updated:** 2025-12-19  
> **Region:** East US 2  
> **Resource Group:** `rg-PULSE-training-prod`

This document describes the Terraform configurations that administrators can adjust for the PULSE platform. All changes are made in `prod.tfvars` and applied via Terraform.

---

## Quick Reference: Common Operations

```bash
# Preview changes
terraform plan -var-file=prod.tfvars

# Apply changes
terraform apply -var-file=prod.tfvars

# Apply without confirmation prompt
terraform apply -var-file=prod.tfvars -auto-approve
```

---

## 1. Azure OpenAI Model Capacity

Adjust AI model throughput (TPM - Tokens Per Minute) for each deployment.

### Configuration Variables

| Variable | Description | Default | Current |
|----------|-------------|---------|---------|
| `openai_deployment_core_chat_capacity` | Persona-Core-Chat (gpt-5-chat) capacity | 5 | 50 |
| `openai_deployment_high_reasoning_capacity` | Persona-High-Reasoning (o4-mini) capacity | 3 | 20 |
| `openai_deployment_audio_realtime_capacity` | PULSE-Audio-Realtime (gpt-4o-realtime-preview) capacity | 2 | 4 |

### Example: Increase Capacity for Demo

```hcl
# prod.tfvars
openai_deployment_core_chat_capacity      = 50   # Main persona conversations
openai_deployment_high_reasoning_capacity = 20   # Evaluation/scoring
openai_deployment_audio_realtime_capacity = 4    # Real-time voice STT/TTS
```

### Quota Limits

**Important:** Capacity is limited by Azure subscription quotas. If you receive an `InsufficientQuota` error:

1. Check current quota: Azure Portal → Cognitive Services → Quotas
2. Request increase: Azure Portal → Help + Support → New Support Request
3. Or reduce the requested capacity to fit within limits

Current known limits (as of 2025-12-19):
- `gpt-4o-realtime-preview`: Quota limit 6 (GlobalStandard)

---

## 2. App Service Configuration

### SKU (Pricing Tier)

| Variable | Description | Default | Options |
|----------|-------------|---------|---------|
| `app_service_sku_name` | App Service Plan SKU | F1 | F1, B1, B2, P1v3, P2v3, P3v3 |

```hcl
# prod.tfvars - Production with VNet integration requires Premium
app_service_sku_name = "P1v3"
```

**Note:** VNet integration requires Premium V3 (P1v3 or higher).

### Enable/Disable App Service

```hcl
# prod.tfvars
enable_app_service = true   # Set to false to disable Web App + Function App
```

---

## 3. Azure Speech Avatar

### Enable/Disable

```hcl
# prod.tfvars
enable_speech_avatar = true   # Deploy Azure Speech Services for real-time avatar
```

### Retrieve API Key

```bash
az cognitiveservices account keys list \
  --name "speech-pulse-training-prod" \
  --resource-group "rg-PULSE-training-prod" \
  --query "key1" -o tsv
```

---

## 4. PostgreSQL Analytics Database

### Configuration Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `analytics_pg_version` | PostgreSQL version | 16 |
| `analytics_pg_sku_name` | Server SKU | GP_Standard_D2s_v3 |
| `analytics_pg_storage_mb` | Storage in MB | 32768 (32 GB) |
| `analytics_pg_backup_retention_days` | Backup retention | 7 |

### Example: Scale Up Database

```hcl
# prod.tfvars
analytics_pg_sku_name  = "GP_Standard_D4s_v3"  # Upgrade to 4 vCores
analytics_pg_storage_mb = 65536                 # Increase to 64 GB
```

### Credentials

```hcl
# prod.tfvars - NEVER commit real passwords
analytics_pg_admin_username = "pulse_analytics_admin"
analytics_pg_admin_password = "CHANGE_ME_STRONG_SECRET"
```

---

## 5. Network Security

### OpenAI Public Network Access

```hcl
# prod.tfvars
# TEMPORARY: Enable for testing, disable for production
openai_public_network_access_enabled = true
```

**Security Note:** Set to `false` for production. When disabled, OpenAI is only accessible via Private Endpoint within the VNet.

### Web App Private Endpoint

```hcl
# prod.tfvars
enable_webapp_private_endpoint = true   # Enable private endpoint for Web App
```

---

## 6. Behavioral Certification Threshold

```hcl
# prod.tfvars
behavioral_mastery_threshold = 0.9   # 90% mastery required (range: 0.85-1.0)
```

---

## 7. Feature Flags

| Variable | Description | Default |
|----------|-------------|---------|
| `enable_app_service` | Deploy Web App + Function App | true |
| `enable_speech_avatar` | Deploy Azure Speech Services | true |
| `enable_visual_asset_deployment` | Deploy Sora-2 (deprecated) | false |
| `enable_webapp_private_endpoint` | Enable Web App private endpoint | true |

---

## 8. Environment Variables (Managed by Terraform)

### Function App Settings

These are automatically configured by Terraform:

| Setting | Description |
|---------|-------------|
| `TRAINING_ORCHESTRATOR_ENABLED` | Enable orchestrator (default: true) |
| `PROMPTS_CONTAINER` | Blob container for session data |
| `AZURE_SPEECH_KEY` | Speech Services API key |
| `AZURE_SPEECH_REGION` | Speech Services region |
| `SCM_DO_BUILD_DURING_DEPLOYMENT` | Enable Oryx build for Python |
| `ENABLE_ORYX_BUILD` | Required for psycopg-binary |

### Web App Settings

| Setting | Description |
|---------|-------------|
| `NEXT_PUBLIC_ENABLE_ADMIN` | Enable admin panel (build-time) |
| `NEXT_PUBLIC_ENV_NAME` | Environment name (build-time) |
| `PORT` | Next.js server port (3000) |

**Important:** `NEXT_PUBLIC_*` variables are build-time only. To change them:
```bash
cd ui
NEXT_PUBLIC_ENABLE_ADMIN=true NEXT_PUBLIC_ENV_NAME=dev npm run build
# Then redeploy the standalone build
```

---

## 9. Deployed Resources Summary

| Resource | Name | Purpose |
|----------|------|---------|
| Resource Group | `rg-PULSE-training-prod` | Container for all resources |
| Azure OpenAI | `cog-PULSE-training-prod` | AI models |
| Speech Services | `speech-pulse-training-prod` | Avatar TTS |
| Web App | `app-PULSE-training-ui-prod` | Next.js UI |
| Function App | `func-PULSE-training-scenario-prod` | Python orchestrator |
| PostgreSQL | `pg-pulse-training-analytics-prod` | Analytics database |
| Storage Account | `pulsetrainingprodsa123` | Blob storage |
| VNet | `vnet-PULSE-training-prod` | Network isolation |
| Log Analytics | `law-PULSE-training-prod` | Logging |
| App Insights | `appi-PULSE-training-prod` | Application monitoring |

---

## 10. Troubleshooting

### Terraform State Issues

```bash
# Refresh state from Azure
terraform refresh -var-file=prod.tfvars

# Import existing resource
terraform import -var-file=prod.tfvars <resource_address> <azure_resource_id>
```

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `InsufficientQuota` | Requested capacity exceeds quota | Reduce capacity or request quota increase |
| `AuthorizationFailed` | Missing RBAC permissions | Activate PIM role or request Contributor access |
| `zone can only be changed...` | PostgreSQL zone mismatch | Set `zone = "2"` in Terraform to match existing |
| `custom_subdomain_name` replacement | Case sensitivity | Use `lower()` for subdomain |

### View Terraform State

```bash
# List all resources
terraform state list

# Show specific resource
terraform state show module.openai.azurerm_cognitive_account.openai
```

---

## 11. File Locations

| File | Purpose |
|------|---------|
| `main.tf` | Root module configuration |
| `variables.tf` | Variable definitions |
| `prod.tfvars` | Production variable values |
| `modules/openai/` | Azure OpenAI module |
| `modules/speech/` | Azure Speech Services module |
| `modules/app/` | Web App + Function App module |
| `modules/analytics_postgres/` | PostgreSQL module |

---

## 12. Applying Changes Workflow

1. **Edit** `prod.tfvars` with desired changes
2. **Preview** changes:
   ```bash
   terraform plan -var-file=prod.tfvars
   ```
3. **Review** the plan output carefully
4. **Apply** changes:
   ```bash
   terraform apply -var-file=prod.tfvars
   ```
5. **Verify** in Azure Portal or via CLI

---

## 13. Backup Before Major Changes

Before making significant infrastructure changes:

```bash
# Export current state
terraform state pull > backup/terraform-state-$(date +%Y%m%d).json

# Backup database (if schema changes)
pg_dump -h pg-pulse-training-analytics-prod.postgres.database.azure.com \
  -U pulse_analytics_admin -d pulse_analytics > backup/db-$(date +%Y%m%d).sql
```
