# Sale Outcome Detection Specification

## Overview

Track whether the trainee successfully "lands the sale" or loses it based on their conversation performance. The AI customer persona should respond realistically - agreeing to buy when the trainee does well, or walking away when they make critical missteps.

## Outcome States

| State | Description | Trigger |
|-------|-------------|---------|
| `in_progress` | Sale still possible | Default state during conversation |
| `won` | Customer agrees to purchase | Trainee completes Earn stage successfully |
| `lost` | Customer walks away | Trainee makes critical misstep(s) |
| `stalled` | Customer hesitates | Trainee skipped steps or was too pushy |

## Win Conditions

The sale is WON when:
1. Trainee reaches Stage 5 (Earn) AND
2. Customer persona responds positively to the close AND
3. No critical missteps occurred during conversation

## Loss Conditions (Missteps)

### Critical Missteps (Immediate Loss Risk)
| Misstep | Detection Pattern | Persona Response |
|---------|-------------------|------------------|
| **Pushy closing too early** | Closing language before Stage 4 | "I'm not ready to decide yet..." |
| **Ignoring stated needs** | Product pitch without referencing customer needs | "That's not really what I'm looking for..." |
| **Overwhelming with options** | Presenting 3+ options at once | "This is too confusing..." |
| **Aggressive pressure** | "You need to decide now", "limited time" | "I don't appreciate being pressured..." |
| **Not listening** | Repeating same pitch after objection | "I already told you that won't work..." |

### Minor Missteps (Accumulate to Loss)
| Misstep | Detection | Impact |
|---------|-----------|--------|
| Skipping discovery questions | No questions in first 2 turns | -1 trust |
| Generic pitch | No personalization | -1 trust |
| Jargon overload | Technical terms without explanation | -1 trust |
| Interrupting | Responding before customer finishes | -1 trust |

**Loss threshold**: 3+ minor missteps OR 1 critical misstep

## Trust Score System

Track a "trust score" that affects sale outcome:

```
Initial trust: 5 (neutral)
Max trust: 10 (very likely to buy)
Min trust: 0 (will walk away)

Trust modifiers:
+1: Good discovery question
+1: Accurate reflection/understanding
+1: Relevant feature-need link
+1: Clear, simple recommendation
+2: Asking for commitment appropriately

-1: Minor misstep
-2: Skipping a PULSE stage
-3: Critical misstep
```

## AI Customer Response Integration

The AI customer persona should:
1. Track trust score internally
2. Respond more positively as trust increases
3. Show hesitation/objections as trust decreases
4. Explicitly agree to buy when trust >= 8 at Stage 5
5. Walk away when trust <= 2

### Example Responses by Trust Level

**High Trust (8-10)**:
- "That sounds perfect, let's do it!"
- "I'm ready to move forward."
- "When can we get started?"

**Medium Trust (4-7)**:
- "I'm still thinking about it..."
- "Can you tell me more about...?"
- "I'm not sure that's right for me."

**Low Trust (1-3)**:
- "I need to think about this more."
- "Maybe I'll come back another time."
- "I don't think this is going to work."

**Lost (0)**:
- "I'm going to look elsewhere."
- "This isn't what I was hoping for."
- "I appreciate your time, but no thanks."

## Implementation

### Backend Changes

1. Add `trust_score` to session state (start at 5)
2. Add `sale_outcome` to session state (`in_progress`, `won`, `lost`, `stalled`)
3. Add `missteps` list to track issues
4. Modify AI prompt to include trust level and respond accordingly
5. Return outcome in chat response

### API Response (Enhanced)

```json
{
  "aiResponse": "...",
  "pulseStage": 5,
  "saleOutcome": {
    "status": "won",
    "trustScore": 9,
    "missteps": [],
    "feedback": "Great job! You successfully completed all PULSE stages."
  }
}
```

### UI Changes

1. Add trust meter visualization (optional)
2. Show sale outcome modal when conversation ends
3. Display feedback on missteps
4. Celebration animation for won sales
5. Coaching tips for lost sales

## Files to Modify

- `orchestrator/chat/__init__.py` - Add trust tracking and outcome detection
- `orchestrator/shared_code/openai_client.py` - Update AI prompt with trust context
- `ui/app/session/page.tsx` - Display outcome and feedback
