# PULSE Progress Automation Specification

## Overview

Automate PULSE selling methodology progress tracking during training conversations. The system should analyze the trainee's (sales associate's) messages and advance through the PULSE stages based on demonstrated behaviors.

## PULSE Framework Stages

| Stage | Name | Key Behaviors | Advancement Criteria |
|-------|------|---------------|---------------------|
| 1 | **P**robe | Ask open-ended questions to understand customer needs | Asked 2+ discovery questions |
| 2 | **U**nderstand | Reflect back, confirm understanding, surface emotions | Demonstrated active listening, paraphrased customer needs |
| 3 | **L**ink | Connect product/solution to stated customer needs | Made explicit connection between product feature and customer need |
| 4 | **S**implify | Narrow options, explain trade-offs clearly | Reduced complexity, presented focused recommendation |
| 5 | **E**arn | Make clear recommendation, ask for commitment | Asked for next step or commitment |

## Implementation Approach

### Option A: Rule-Based Detection (Fast, Simple)
- Pattern matching on trainee messages
- Look for question marks, reflection phrases, product mentions, closing language
- Pros: Fast, no additional API calls
- Cons: Less accurate, may miss nuanced behaviors

### Option B: AI-Powered Analysis (Accurate, Slower)
- Use LLM to analyze conversation and determine current stage
- Include PULSE criteria in prompt
- Pros: More accurate, understands context
- Cons: Additional latency, API cost

### Recommended: Hybrid Approach
1. **Quick rule-based check** for obvious stage indicators
2. **AI analysis** included in the main chat response generation
3. Return both the AI response AND the detected PULSE stage

## API Changes

### Chat Endpoint Response (Enhanced)

```json
{
  "aiResponse": "AI's response text",
  "avatarEmotion": "neutral|happy|concerned|...",
  "sessionId": "uuid",
  "pulseStage": 1-5,
  "pulseAnalysis": {
    "currentStage": "Probe",
    "stageProgress": 0.6,
    "detectedBehaviors": ["asked open-ended question", "explored customer needs"],
    "nextStepHint": "Try to reflect back what the customer said to show understanding"
  }
}
```

## Stage Detection Logic

### Stage 1: Probe
Trainee is asking discovery questions:
- Contains question marks
- Uses words like: "what", "how", "tell me", "describe", "explain"
- Avoids product pitching in first few turns

### Stage 2: Understand  
Trainee demonstrates active listening:
- Uses reflection phrases: "so you're saying", "it sounds like", "I hear that"
- Paraphrases customer concerns
- Acknowledges emotions: "I understand", "that makes sense"

### Stage 3: Link
Trainee connects solution to needs:
- References something customer said earlier
- Uses phrases like: "based on what you said", "since you mentioned", "that's why"
- Explains how feature addresses specific need

### Stage 4: Simplify
Trainee narrows focus:
- Presents limited options (1-2 recommendations)
- Uses comparison language: "compared to", "the difference is"
- Explains trade-offs in simple terms

### Stage 5: Earn
Trainee asks for commitment:
- Uses closing language: "would you like", "shall we", "ready to"
- Proposes next step: "let's schedule", "I can set that up"
- Asks for decision: "what do you think", "does that work for you"

## Conversation Flow Example

```
Turn 1 (Trainee): "Hi, I'm Rob. What brings you in today?" 
→ Stage 1 (Probe) - Asked open question

Turn 2 (Trainee): "So you're having trouble sleeping and want something that helps with back pain?"
→ Stage 2 (Understand) - Reflected back needs

Turn 3 (Trainee): "Since you mentioned back pain, our Sleep Number beds let you adjust firmness..."
→ Stage 3 (Link) - Connected feature to stated need

Turn 4 (Trainee): "Based on what you've told me, I'd recommend the p5 - it has the adjustability you need without the extra features you won't use."
→ Stage 4 (Simplify) - Narrowed to specific recommendation

Turn 5 (Trainee): "Would you like to try it out? I can set up a quick demo right now."
→ Stage 5 (Earn) - Asked for commitment
```

## Implementation Steps

1. Add `_analyze_pulse_stage()` function to chat endpoint
2. Include PULSE analysis prompt in system message
3. Parse AI response for stage indicators
4. Track stage in session storage
5. Return stage in API response
6. Update UI to use returned stage

## Files to Modify

- `orchestrator/chat/__init__.py` - Add PULSE analysis
- `orchestrator/shared_code/openai_client.py` - Add analysis prompt helper
- `ui/app/session/page.tsx` - Use returned pulseStage
- `ui/components/SbnProgressBar.tsx` - No changes needed (already accepts currentStep prop)
