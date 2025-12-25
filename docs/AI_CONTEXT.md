# PULSE Training Platform - AI Context Document

> **Purpose**: This document helps AI assistants quickly understand the PULSE Training Platform codebase and resume work efficiently.

## Project Overview

**PULSE Training Platform** is a sales training application that uses AI-powered avatars to simulate customer interactions. Trainees practice the **PULSE Selling methodology** (a 5-step sales framework) with realistic AI personas.

### PULSE Selling Framework (5 Steps)
1. **Probe** - Ask discovery questions to understand customer needs
2. **Understand** - Demonstrate understanding of customer's situation
3. **Link** - Connect product features to customer needs
4. **Simplify** - Make the solution easy to understand
5. **Earn** - Earn the commitment/close the sale

## Architecture

### Frontend (Next.js 14 - App Router)
- **Location**: `/ui/`
- **Framework**: Next.js 14 with TypeScript, Tailwind CSS
- **Deployment**: Azure App Service (standalone output mode)

### Backend (Azure Functions - Python)
- **Location**: `/orchestrator/`
- **Runtime**: Python 3.11
- **Deployment**: Azure Function App

### Infrastructure (Terraform)
- **Location**: Root directory (`main.tf`, `modules/`)
- **Resources**: Azure OpenAI, Speech Services, PostgreSQL, Storage, App Service

## Key Application Areas

### 1. Training Flow (`/training`)
- Users select experience level and scenario
- Practice PULSE methodology with AI avatar
- Real-time speech recognition and avatar responses

### 2. Session Flow (`/session`)
- Live conversation with AI persona
- Speech-to-text → LLM response → Text-to-speech
- Azure Speech Avatar for visual representation

### 3. Admin Panel (`/admin`)
- **Avatars** (`/admin/avatars`) - Download/manage LiteAvatar models
- **AI Components** (`/admin/ai`) - Configure prompts and agents
- **Training Admin** (`/admin/training`) - Manage training content
- **Auth & Security** (`/admin/auth`) - User management, roles, SSO
- **Log Management** (`/admin/logs`) - AI log search and Cribl Stream integration

### 4. Feedback (`/feedback`)
- Post-session scoring and analysis
- BCE/MCF/CPO evaluation framework
- PULSE step-by-step performance review

## Authentication System

### Auth Types
- **SSO Mode**: Azure AD / Microsoft Entra ID (production)
- **Demo Mode**: Local authentication with demo/demo credentials

### User Roles (5 levels)
1. `super_admin` - Full system access (break glass account)
2. `admin` - Manage users, settings, content
3. `manager` - Manage trainees, view reports
4. `trainer` - Conduct training, provide feedback
5. `trainee` - Access training content and sessions

### Key Auth Files
- `/ui/components/AuthContext.tsx` - Auth provider and hooks
- `/ui/types/auth.ts` - Type definitions, role definitions, preset users
- `/ui/lib/auth-db.ts` - Database operations for auth

## Avatar System

### Avatar Sources
- **ModelScope LiteAvatars** - Pre-built realistic avatars from HumanAIGC-Engineering
- **Azure Speech Avatar** - Real-time WebRTC streaming for conversations

### Avatar Management Files
- `/ui/app/admin/avatars/page.tsx` - Avatar management UI
- `/ui/app/api/orchestrator/avatars/catalog/route.ts` - Catalog API with hide/show
- `/ui/app/api/orchestrator/avatars/local/route.ts` - Downloaded avatars API
- `/ui/app/api/orchestrator/avatars/download/route.ts` - Download from ModelScope

### Avatar Data Storage
- **Catalog metadata**: `/ui/data/avatars/metadata.json`
- **Hidden avatars**: `/ui/data/avatars/hidden-avatars.json`
- **Avatar files**: `/ui/data/avatars/{avatar-id}/`

## Key Configuration

### Environment Variables (UI)
```
NEXT_PUBLIC_ENV_NAME=dev|staging|prod
NEXT_PUBLIC_ENABLE_ADMIN=true
NEXT_PUBLIC_ENABLE_TRAINING=true
FUNCTION_APP_BASE_URL=https://...
AZURE_AD_CLIENT_ID=...
AZURE_AD_CLIENT_SECRET=...
AZURE_AD_TENANT_ID=...
```

### Environment Variables (Function App)
```
OPENAI_ENDPOINT=https://...
AZURE_OPENAI_API_KEY=...
OPENAI_DEPLOYMENT_PERSONA_CORE_CHAT=...
OPENAI_DEPLOYMENT_PERSONA_HIGH_REASONING=...
AZURE_SPEECH_KEY=...
AZURE_SPEECH_REGION=eastus2
TRAINING_ORCHESTRATOR_ENABLED=true
```

## Recent Changes (2025-12-24)

### Avatar Manager
- Added delete/hide functionality for catalog avatars
- File-based storage for hidden avatars (`hidden-avatars.json`)
- Differentiated UX for deleting downloaded vs hiding catalog avatars

### Training Page
- Fixed user info card to show actual logged-in user (was hardcoded "Demo User")
- Uses `useAuth()` hook to get user name and compute initials

### Log Management & Cribl Integration
- Added Log Management admin page with Cribl Stream configuration
- Created logging utility (`/ui/lib/logger.ts`) for application-wide use
- Supports system, application, and behavioral log types
- Test Connection feature for validating Cribl configuration

## Common Development Tasks

### Build and Deploy UI
```bash
cd ui
npm run build
# Creates .next/standalone for Azure App Service
```

### Run Locally
```bash
cd ui
npm run dev  # Starts on http://localhost:3000
```

### Deploy to Azure
```bash
cd ui
npm run build
cd .next/standalone
zip -r ../../deploy.zip .
az webapp deployment source config-zip \
  --resource-group "rg-PULSE-training-prod" \
  --name "app-PULSE-training-ui-prod" \
  --src deploy.zip
```

## File Structure Quick Reference

```
pulseapp/
├── ui/                           # Next.js frontend
│   ├── app/                      # App Router pages
│   │   ├── admin/               # Admin panel pages
│   │   ├── training/            # Training flow
│   │   ├── session/             # Live session
│   │   ├── feedback/            # Post-session feedback
│   │   └── api/                 # API routes (proxies to orchestrator)
│   ├── components/              # React components
│   ├── types/                   # TypeScript types
│   └── lib/                     # Utilities and DB operations
├── orchestrator/                # Azure Functions backend
│   ├── session_start/           # Session initialization
│   ├── audio_chunk/             # Audio processing
│   ├── feedback_session/        # Feedback retrieval
│   └── shared_code/             # Shared utilities
├── modules/                     # Terraform modules
├── docs/                        # Documentation
├── aidocs/                      # AI/workflow documentation
├── CHANGELOG.md                 # Development history
└── AI_CONTEXT.md               # This file
```

## Useful Patterns

### Getting Current User
```typescript
import { useAuth } from "@/components/AuthContext";
const { user, isAuthenticated, authMode } = useAuth();
// user?.name, user?.email, user?.role
```

### Protected Routes
```typescript
import { RequireAuth } from "@/components/AuthContext";
<RequireAuth permission="users:view">
  <ProtectedContent />
</RequireAuth>
```

### API Route to Orchestrator
```typescript
// Proxy pattern in /ui/app/api/orchestrator/*/route.ts
const response = await fetch(`${FUNCTION_APP_BASE_URL}/endpoint`, {
  method: request.method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(data),
});
```

### Using the Logger
```typescript
import { logger } from '@/lib/logger';

// Application logs
logger.info('User logged in', { userId: '123', source: 'auth' });
logger.error('Failed to load data', { error: err.message });

// Behavioral logs (training metrics)
logger.behavioral('Training session completed', { userId: '123', score: 85 });

// System logs
logger.infoSystem('Server started', { source: 'startup' });
```

## Known Issues / Technical Debt

1. Avatar download requires ModelScope connectivity (China-based CDN)
2. Some orchestrator endpoints still return stub data (BCE/MCF/CPO scoring)
3. Real-time audio pipeline works but avatar lip-sync timing needs optimization

---
*Last updated: 2025-12-24*
