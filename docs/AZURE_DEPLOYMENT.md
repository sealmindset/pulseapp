# Azure Deployment Guide

This document covers deployment requirements and best practices for running PULSE in Azure. All components are designed to run 100% in Azure on Linux-based services.

## Architecture Overview

| Component | Azure Service | Runtime | Notes |
|-----------|--------------|---------|-------|
| UI (Next.js) | App Service (Web App) | Node.js 18 LTS (Linux) | Standalone output mode |
| Orchestrator | Function App | Python 3.11 (Linux) | Consumption plan |
| Storage | Blob Storage | N/A | Private endpoints |
| AI Services | Azure OpenAI | N/A | Private endpoints |
| Speech | Azure Speech Services | N/A | Avatar + STT |

## Critical: Linux vs macOS Deployment

**All Azure services run on Linux.** When deploying from a macOS development machine, be aware of these platform-specific issues:

### Python Function App (Orchestrator)

**Problem:** Python packages with native binaries (e.g., `cryptography`, `psycopg-binary`) compiled on macOS are incompatible with Linux.

**Symptoms:**
```
ImportError: /home/site/wwwroot/.python_packages/lib/site-packages/cryptography/hazmat/bindings/_rust.abi3.so: invalid ELF header
```

**Solution:** Always use remote build for Python Function Apps:

```bash
# CORRECT: Let Azure build packages on Linux
az functionapp deployment source config-zip \
  --resource-group "rg-PULSE-training-prod" \
  --name "func-pulse-training-scenario-prod" \
  --src orchestrator.zip \
  --build-remote true

# Required app settings for remote build
az functionapp config appsettings set \
  --resource-group "rg-PULSE-training-prod" \
  --name "func-pulse-training-scenario-prod" \
  --settings "SCM_DO_BUILD_DURING_DEPLOYMENT=true" \
             "ENABLE_ORYX_BUILD=true" \
             "WEBSITE_RUN_FROM_PACKAGE=0"
```

**NEVER** include `.python_packages/` in your deployment zip when deploying from macOS:

```bash
# Create deployment zip WITHOUT local packages
cd orchestrator
zip -r ../orchestrator.zip . \
  -x "*.pyc" \
  -x "__pycache__/*" \
  -x ".venv/*" \
  -x "*.git*" \
  -x ".python_packages/*"
```

### Next.js Web App (UI)

The UI uses Next.js standalone output which is platform-independent (pure JavaScript). However, ensure:

1. Build with `output: 'standalone'` in `next.config.mjs`
2. Copy static files after build:
   ```bash
   cp -r ui/.next/static ui/.next/standalone/.next/
   ```
3. Deploy the standalone folder:
   ```bash
   cd ui/.next/standalone
   zip -r ../../../ui-standalone.zip .
   ```

## Deployment Commands

### Function App (Orchestrator)

```bash
# 1. Create deployment zip (exclude local packages)
cd orchestrator
rm -rf .python_packages  # Remove any local packages
zip -r ../orchestrator.zip . -x "*.pyc" -x "__pycache__/*" -x ".venv/*" -x ".python_packages/*"

# 2. Deploy with remote build
az functionapp deployment source config-zip \
  --resource-group "rg-PULSE-training-prod" \
  --name "func-pulse-training-scenario-prod" \
  --src orchestrator.zip \
  --build-remote true

# 3. Restart to pick up changes
az functionapp restart \
  --resource-group "rg-PULSE-training-prod" \
  --name "func-pulse-training-scenario-prod"
```

### Web App (UI)

```bash
# 1. Build Next.js
cd ui
npm run build

# 2. Prepare standalone deployment
cp -r .next/static .next/standalone/.next/
cd .next/standalone
zip -r ../../../ui-standalone.zip .

# 3. Deploy via zip deploy
curl -X POST \
  "https://app-pulse-training-ui-prod.scm.azurewebsites.net/api/zipdeploy" \
  -u '$app-PULSE-training-ui-prod:<deployment-password>' \
  --data-binary @ui-standalone.zip \
  -H "Content-Type: application/zip"

# 4. Restart
az webapp restart \
  --resource-group "rg-PULSE-training-prod" \
  --name "app-PULSE-training-ui-prod"
```

## Environment Variables

### Function App Required Settings

| Variable | Description | Example |
|----------|-------------|---------|
| `OPENAI_ENDPOINT` | Azure OpenAI endpoint | `https://cog-pulse-training-prod.openai.azure.com` |
| `AZURE_OPENAI_API_KEY` | Azure OpenAI API key | (secret) |
| `OPENAI_API_VERSION` | API version | `2024-10-01-preview` |
| `OPENAI_DEPLOYMENT_PERSONA_CORE_CHAT` | Chat model deployment | `Persona-Core-Chat` |
| `AZURE_SPEECH_KEY` | Speech Services key | (secret) |
| `AZURE_SPEECH_REGION` | Speech Services region | `eastus2` |
| `SCM_DO_BUILD_DURING_DEPLOYMENT` | Enable remote build | `true` |
| `ENABLE_ORYX_BUILD` | Enable Oryx builder | `true` |

### Web App Required Settings

| Variable | Description | Example |
|----------|-------------|---------|
| `FUNCTION_APP_BASE_URL` | Function App URL with /api | `https://func-pulse-training-scenario-prod.azurewebsites.net/api` |
| `NEXT_PUBLIC_ENV_NAME` | Environment name | `prod` |

## Troubleshooting

### Check Function App Logs

```bash
az monitor app-insights query \
  --app "appi-PULSE-training-prod" \
  --resource-group "rg-PULSE-training-prod" \
  --analytics-query "traces | where timestamp > ago(10m) | order by timestamp desc | take 20"
```

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `invalid ELF header` | macOS packages deployed to Linux | Use `--build-remote true` |
| `No module named 'xyz'` | Missing dependency | Check `requirements.txt`, redeploy with remote build |
| `400 Bad Request` from OpenAI | Token limit exceeded | Limit conversation history |
| `WebSocket 1006` | Avatar connection dropped | Token expiration or service limit |

### Verify Deployment

```bash
# Test Function App health
curl -s "https://func-pulse-training-scenario-prod.azurewebsites.net/api/health"

# Test session start
curl -s -X POST \
  "https://func-pulse-training-scenario-prod.azurewebsites.net/api/session/start" \
  -H "Content-Type: application/json" \
  -d '{"scenarioId":"test","personaType":"Socializer"}'
```

## CI/CD Recommendations

For automated deployments, use GitHub Actions with:

1. **Python Function App**: Use `azure/functions-action@v1` with `enable-oryx-build: true`
2. **Next.js Web App**: Build in CI, then deploy standalone output

Example workflow snippet:

```yaml
- name: Deploy Function App
  uses: azure/functions-action@v1
  with:
    app-name: func-pulse-training-scenario-prod
    package: orchestrator.zip
    enable-oryx-build: true
```

## Version History

- **2025-12-19**: Added Linux deployment requirements, remote build documentation
- **2025-12-19**: Fixed Python package compatibility issues (cryptography, psycopg)
- **2025-12-19**: Added conversation history limits to prevent token overflow
