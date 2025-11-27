# Phase 0 – PULSE Training Business Readiness Assessment

This document defines the **Phase 0 assessment** to determine whether the **current build** of the PULSE Simulation Engine and UI meets the business requirements for training sales teams on the PULSE methodology.

Phase 0 is **assessment only**:

- No runtime code, schema, or Terraform changes.
- Output is a written determination of readiness and a list of functional gaps.

---

## 1. Objectives

- **O1 – PULSE Methodology Fidelity**
  - Confirm the app executes the PULSE steps (Connect & Discover, Guide & Curate, Individualize, Address & Close Today, Confirm & Reassure, Follow Up & Advocate) in a way that matches the prompts and trainer documentation.
- **O2 – Persona Coverage**
  - Confirm realistic behavior and scoring for the 4 core personas:
    - Thinker, Socializer, Relater, Director.
- **O3 – Outcome Coverage**
  - For each persona, validate representative:
    - FAILURE, PARTIAL SUCCESS, SUCCESS scenarios.
- **O4 – Scoring & Debrief Quality**
  - Confirm BCE/MCF/CPO scoring and trainer debriefs are:
    - Aligned with `aidocs/trainer_prompts.md`.
    - Clear enough to coach sales reps.
- **O5 – Admin UX Readiness**
  - Confirm prompt/scenario CRUD is usable and stable for non-engineering operators.
- **O6 – Infra & Performance Sanity**
  - Confirm Azure Functions, Azure OpenAI, and Storage are sufficient for a pilot training load (no obvious bottlenecks at low/moderate scale).

---

## 2. Test Matrix – Personas × Outcomes

Each row is a **manual or semi-automated run** of the simulation with a defined input pattern and expected qualitative outcome. Use the Thinker / Socializer / Relater / Director scenario designs as guidance for constructing or selecting concrete test runs.

### 2.1 Summary Table

| ID | Persona     | Outcome Type      | Goal                                                      |
|----|-------------|-------------------|-----------------------------------------------------------|
| T-TH-F | Thinker    | FAILURE           | Logic-focused customer; trainee under-discovers, fails to justify. |
| T-TH-P | Thinker    | PARTIAL SUCCESS   | Some analytical needs met; weak close or misaligned risk framing. |
| T-TH-S | Thinker    | SUCCESS           | Strong analytical framing, clear justification, confident close. |
| T-SO-F | Socializer | FAILURE           | Conversation stays in chatter; no clear guide/close.      |
| T-SO-P | Socializer | PARTIAL SUCCESS   | High engagement, deferred decision with plausible follow-up. |
| T-SO-S | Socializer | SUCCESS           | Fun, social-proof driven close with clear today-commitment. |
| T-RE-F | Relater    | FAILURE           | Trainee triggers conflict anxiety, applies pressure.      |
| T-RE-P | Relater    | PARTIAL SUCCESS   | Good empathy, but no concrete commitment or path.        |
| T-RE-S | Relater    | SUCCESS           | Soft close that protects joint decision and harmony.      |
| T-DI-F | Director   | FAILURE           | Time wasted, vague info, no clear comparison / numbers.   |
| T-DI-P | Director   | PARTIAL SUCCESS   | Structured comparison, rational case, deposit/hold only.  |
| T-DI-S | Director   | SUCCESS           | Clear priorities, ROI framing, explicit decision today.   |

> **Note:** For each ID, you may either:
> - Use a deterministic scripted conversation (if available), or
> - Drive the UI/agent prompts to elicit a matching pattern manually, then record the outputs.

---

## 3. PULSE Flow Checks per Scenario

For **each matrix row**, verify the following:

### 3.1 PULSE Step Log Presence

- Each session should emit a **step log** covering:
  - Step names in order: `Connect & Discover`, `Guide & Curate`, `Individualize`, `Address & Close Today`, `Confirm & Reassure`, `Follow Up & Advocate`.
  - A per-step summary of:
    - What the trainee attempted.
    - Why it was or was not effective for the persona.

**Pass Criteria:**

- All six steps are present in the log.
- Narrative is consistent with the scenario’s dialogue.
- Failure scenarios explicitly call out **which steps broke down and why**.

### 3.2 BCE / MCF / CPO Scoring

For each scenario, confirm:

- Scores are emitted for:
  - **BCE** (Behavioral Compliance Evaluator).
  - **MCF** (Methodology & Content Fidelity).
  - **CPO** (Conversion & Psychological Outcome).
- A consolidated mastery score and pass/fail decision is produced according to the rules in `aidocs/trainer_prompts.md`.

**Qualitative Range Check:**

- **FAILURE** scenarios:
  - BCE: typically < 0.6
  - MCF: typically < 0.6
  - CPO: low (e.g., < 0.4); `CONVERSION_SUCCESS: NO`.
- **PARTIAL SUCCESS** scenarios:
  - At least one of BCE/MCF moderate (≈ 0.7–0.8), but aggregate below pass threshold.
  - CPO reflects ambiguity (e.g., deposit-only, weak follow-up). No or low-confidence conversion.
- **SUCCESS** scenarios:
  - Aggregate mastery ≥ 0.85.
  - `CONVERSION_SUCCESS: YES` with persona-appropriate close.

**Pass Criteria:**

- Scores and pass/fail decisions **align qualitatively** with the actual dialogue and persona pattern.
- No obvious contradictions (e.g., high CPO on a scenario where the customer clearly walks away).

### 3.3 Trainer Debrief Utility

For each scenario, review the trainer-facing debrief:

- Contains:
  - 2–6 specific behavioral observations.
  - Clear articulation of **what went wrong / right** per PULSE step.
  - At least 2 actionable improvement suggestions.
- Written in language suitable for a sales coach (not just an LLM internal prompt).

**Pass Criteria:**

- A trainer could read the debrief and immediately coach a rep on:
  - Persona adaptation.
  - PULSE step execution.
  - Closing behavior.

---

## 4. Admin UX Assessment

### 4.1 Prompt & Scenario CRUD

Test the admin flows (via Next.js admin UI or direct API if UI is not ready):

1. **Create** a new prompt/scenario configuration.
2. **Update** a field (e.g., tweak wording, change weighting).
3. **Delete** or disable a scenario/prompt safely.

For each operation, record:

- How an operator knows **what changed** and where it applies.
- How errors are presented (even if currently plain text).
- Whether there is any visible lag / inconsistency between admin changes and runtime behavior.

**Pass Criteria:**

- An informed non-engineering operator could reasonably:
  - Understand which prompts control which flows.
  - Make safe edits without breaking the system.
- Any confusing behavior is documented as a gap to address in later phases.

---

## 5. Infra & Performance Sanity

This is a **lightweight check**, not a full load test.

### 5.1 Basic Load Trial

- Run a small batch of sessions (e.g., 10–30) spread across personas.
- Observe:
  - Function execution durations.
  - Azure OpenAI latency.
  - Any throttling / quota messages.

**Pass Criteria:**

- No frequent timeouts or 5xx errors under this light load.
- No obvious Azure capacity constraints for a pilot.

### 5.2 Storage Behavior

- Confirm prompt/scenario data is being persisted as expected in Storage.
- Spot-check a few blobs for structure and stability.

**Pass Criteria:**

- No evidence of data corruption or missing records during basic operations.

---

## 6. Findings & Readiness Decision Template

At the end of Phase 0, populate this section.

### 6.1 Summary of Findings

- **PULSE Fidelity:**
  - [ ] Fully aligned with trainer documentation
  - [ ] Partially aligned (describe gaps):
- **Persona Coverage:**
  - [ ] Thinker – OK / Gaps:
  - [ ] Socializer – OK / Gaps:
  - [ ] Relater – OK / Gaps:
  - [ ] Director – OK / Gaps:
- **Outcome Coverage (F/P/S per persona):**
  - [ ] All represented and sensible
  - [ ] Missing or misaligned cases (list):
- **Scoring & Debrief Quality:**
  - [ ] Scores and debriefs support real coaching
  - [ ] Gaps (e.g., vague feedback, mis-weighting):
- **Admin UX:**
  - [ ] Usable for non-engineering operators
  - [ ] Gaps (e.g., unclear mapping, poor errors):
- **Infra & Performance:**
  - [ ] Sufficient for pilot
  - [ ] Concerns (e.g., latency, stability):

### 6.2 Readiness Decision

> **Decision:**
>
> - [ ] Current build is **ready for pilot PULSE training** as-is.
> - [ ] Current build is **not yet ready**; requires the following fixes before pilot:
>   - ...

### 6.3 Links / Artifacts

- Links to captured session logs and outputs for each Test ID.
- Any screenshots / JSON exports used in the assessment.

---

## 7. Next Steps Post–Phase 0

Depending on the decision:

- If **Ready for Pilot**:
  - Proceed to **Phase 1–4** hardening with confidence that functional behavior is acceptable.
- If **Not Ready**:
  - Create targeted issues for each identified gap:
    - e.g., "Relater PARTIAL SUCCESS scenario mis-scores BCE as success," or
    - "Director SUCCESS path missing clear ROI explanation in debrief."
  - Address those in a **pre–Phase 1** bugfix pass, then re-run the relevant parts of this assessment.
