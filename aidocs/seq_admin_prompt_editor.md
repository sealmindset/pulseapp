# Sequence Diagram — Admin Prompt Editor (Dev Mode)

```mermaid
sequenceDiagram
    autonumber
    participant U as Admin User (Dev)
    participant UI as Browser UI (/admin)
    participant API as Next.js Proxy (/api/orchestrator/admin/*)
    participant FA as Function App (Orchestrator)
    participant ST as Azure Blob Storage (prompts container)

    note over UI: Admin UI visible only when NEXT_PUBLIC_ENABLE_ADMIN=true and NEXT_PUBLIC_ENV_NAME!=prod
    note over FA: Writes gated by ADMIN_EDIT_ENABLED=true in dev

    U->>UI: Open /admin
    UI->>API: GET /admin/prompts
    API->>FA: GET /admin/prompts
    FA->>ST: List prompts/* and read current prompt JSONs
    ST-->>FA: Prompt summaries
    FA-->>API: { items: [ ... ] }
    API-->>UI: { items: [ ... ] }
    UI->>UI: Render prompt list

    alt Create new prompt
        U->>UI: Click New → Edit fields → Save
        UI->>API: POST /admin/prompts { title, type, agentId?, content }
        API->>FA: POST /admin/prompts
        FA->>ST: Write prompts/{id}.json v1 and prompts/{id}/versions/1.json
        FA-->>API: 201 Saved prompt
        API-->>UI: 201 Saved prompt
        UI->>UI: Refresh list
    else Edit existing prompt
        U->>UI: Select prompt → Edit → Save
        UI->>API: PUT /admin/prompts/{id} { ...updated fields... }
        API->>FA: PUT /admin/prompts/{id}
        FA->>ST: Bump version; write current and versioned copy
        FA-->>API: 200 Updated prompt
        API-->>UI: 200 Updated prompt
    else Delete prompt (soft)
        U->>UI: Delete prompt
        UI->>API: DELETE /admin/prompts/{id}
        API->>FA: DELETE /admin/prompts/{id}
        FA->>ST: Mark deleted=true, version bump; write current + versioned
        FA-->>API: { ok: true }
        API-->>UI: { ok: true }
    end

    U->>UI: View versions
    UI->>API: GET /admin/prompts/{id}/versions
    API->>FA: GET /admin/prompts/{id}/versions
    FA->>ST: List prompts/{id}/versions/*.json
    ST-->>FA: Version list with metadata
    FA-->>API: { items: [ {version, updatedAt, updatedBy}, ... ] }
    API-->>UI: { items: [...] }
    UI->>UI: Render versions list with open links
```
