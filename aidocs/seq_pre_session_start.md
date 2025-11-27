# Sequence Diagram — Pre-Session Start

```mermaid
sequenceDiagram
    autonumber
    participant U as User
    participant UI as Browser UI (Pre-Session)
    participant API as Next.js Proxy (/api/orchestrator/session/start)
    participant FA as Function App (Orchestrator)
    participant AOI as Azure OpenAI (Visual Asset)
    participant ST as Azure Blob Storage

    U->>UI: Select persona + accept prerequisites
    UI->>API: POST { persona, filters, prerequisitesAccepted }
    API->>FA: POST /session/start
    opt Generate avatar (optional)
        FA->>AOI: Generate Persona-Visual-Asset
        AOI-->>FA: Avatar image
        FA->>ST: Save avatar + initialize session
    end
    FA-->>API: { sessionId, avatarUrl? }
    API-->>UI: { sessionId, avatarUrl? }
    UI->>UI: setSessionId, setAvatarUrl
    UI->>UI: navigate to /session

    Note over FA,AOI: Private Endpoint + Private DNS; no public access
```
