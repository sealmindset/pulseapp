# Sequence Diagram — Complete Session

```mermaid
sequenceDiagram
    autonumber
    participant U as User
    participant UI as Browser UI (Session)
    participant API as Next.js Proxy (/api/orchestrator/session/complete)
    participant FA as Function App (Orchestrator)
    participant MAN as Orchestrator Manager (Agentic AI)
    participant BCE as Agent: Behavioral Compliance Evaluator
    participant MCF as Agent: Methodology Fidelity Checker
    participant CPO as Agent: Conversion Outcome Assessor
    participant ST as Azure Blob Storage

    U->>UI: Click "Complete Session"
    UI->>API: POST { sessionId }
    API->>FA: POST /session/complete

    FA->>MAN: Begin evaluation orchestration
    MAN->>BCE: Evaluate behavioral compliance (transcript, persona)
    MAN->>MCF: Evaluate methodology & content fidelity
    MAN->>CPO: Evaluate conversion & psychological outcome
    BCE-->>MAN: Score + summary (BCE)
    MCF-->>MAN: Score + summary (MCF)
    CPO-->>MAN: Score + summary + conversion flag (CPO)
    MAN->>MAN: Weighted aggregate (BCE 40%, MCF 35%, CPO 25%)
    MAN->>ST: Persist final scorecard + artifacts (JSON, transcript, audio)

    FA-->>API: 200/204 (ack)
    API-->>UI: 200/204 (ack)
    UI->>UI: navigate to /feedback

    Note over FA,MAN,BCE,MCF,CPO: Private networking (VNet + Private Endpoints). No direct UI access.
```
