# PULSE Training Platform - Testing Cheatsheet

This guide shows how to test the app through the UI/UX to demonstrate **PASS** and **FAIL** scenarios.

---

## Quick Start

1. **Login**: Go to `/` and use credentials `demo` / `demo`
2. **Pre-Session**: Select a persona and check the prerequisites box
3. **Start Session**: Click "Start Session" to begin

---

## Testing PULSE Stage Progression

Start a new session (to reset stage to 1), then try these phrases in order:

| Say This | Expected Stage | What It Tests |
|----------|----------------|---------------|
| "Hi! What brings you in today?" | 1 → 2 (Probe complete) | Initial greeting + discovery question |
| "So you're saying you need better sleep because of back pain?" | 2 → 3 (Understand complete) | Paraphrasing + identifying pain points |
| "Since you mentioned back pain, our Sleep Number beds adjust to your exact comfort level" | 3 → 4 (Link complete) | Connecting features to customer needs |
| "Based on what you've shared, I'd recommend the p5 for your needs" | 4 → 5 (Simplify complete) | Making a professional recommendation |
| "Would you like to try it out today?" | Stay at 5 (Earn) | Closing attempt |

**Expected Result**: The progress bar should advance one step at a time!

---

## Testing a PASSING Session

### Scenario: Successful Sale with Relater Persona

1. Select **Relater** persona (beginner difficulty)
2. Start session
3. Follow this conversation flow:

| Your Message | Why It Works |
|--------------|--------------|
| "Hi there! Welcome in. What brings you to Sleep Number today?" | Warm greeting + open-ended question |
| "I hear you - getting quality sleep is so important. Tell me more about what's been keeping you up?" | Empathy + deeper discovery |
| "So it sounds like your back pain is really affecting your sleep quality. That must be frustrating." | Active listening + emotional validation |
| "You know, our beds are designed exactly for situations like yours. The adjustable firmness can really help with back support." | Linking solution to their specific need |
| "Based on everything you've shared, I think the p5 would be perfect. It has the adjustability you need at a great value." | Professional recommendation |
| "I'd love to help you get started today. We have some great financing options that make it easy." | Soft close with value |

**Expected Outcome**:
- Trust score stays high (7-10)
- Progress through all 5 PULSE stages
- Sale outcome: **WON** ✅
- Feedback page shows passing score (≥70%)

---

## Testing a FAILING Session

### Scenario: Lost Sale Due to Missteps

1. Select **Director** persona (expert difficulty)
2. Start session
3. Try these missteps:

| Your Message | What Goes Wrong |
|--------------|-----------------|
| "You should buy our best-selling bed today!" | Pushy close before discovery |
| "This deal ends today, you don't want to miss out!" | Pressure tactics |
| "Our i10 is amazing, everyone loves it" | Ignoring customer needs |
| "Trust me, this is what you need" | Not listening |

**Expected Outcome**:
- Trust score drops rapidly (below 3)
- Customer walks away
- Sale outcome: **LOST** ❌
- Feedback page shows failing score (<70%)

---

## Missteps That Hurt Trust

These behaviors trigger trust penalties:

| Misstep | Trust Penalty | Example Phrase |
|---------|---------------|----------------|
| **Pushy early close** | -3 | "Buy now!" before Stage 4 |
| **Pressure tactics** | -3 | "Limited time offer!" / "Deal ends today!" |
| **Ignoring needs** | -2 | "Our best seller is..." without asking questions |
| **Interrupting** | -2 | Cutting off the customer mid-sentence |
| **Being dismissive** | -2 | "That's not really an issue" |
| **Aggressive upselling** | -2 | Pushing expensive options without justification |

### Trust Score Thresholds

| Trust Level | Score Range | Customer Behavior |
|-------------|-------------|-------------------|
| 🟢 High | 7-10 | Engaged, receptive, likely to buy |
| 🟡 Medium | 4-6 | Hesitant, needs reassurance |
| 🔴 Low | 0-3 | Defensive, may walk away |

**Critical**: If trust drops to 0, the customer walks away and the sale is **LOST**.

---

## Testing by Persona

Each persona responds differently to your approach:

### Director (Expert Difficulty) 👔
- **Wants**: Efficiency, facts, bottom-line results
- **Hates**: Small talk, emotional language, wasting time
- **Test phrases that work**: "Let me get straight to the point..." / "Here are the key specs..."
- **Test phrases that fail**: "How's your day going?" / "Let me tell you a story..."

### Relater (Beginner Difficulty) 🤝
- **Wants**: Trust, patience, personal connection
- **Hates**: Pressure, rushing, aggressive sales
- **Test phrases that work**: "Take your time..." / "I understand how you feel..."
- **Test phrases that fail**: "You need to decide now" / "What's holding you back?"

### Socializer (Moderate Difficulty) 🎉
- **Wants**: Enthusiasm, recognition, excitement
- **Hates**: Boring presentations, being ignored
- **Test phrases that work**: "That's a great point!" / "You have excellent taste!"
- **Test phrases that fail**: Monotone responses, ignoring their stories

### Thinker (Challenging Difficulty) 🔬
- **Wants**: Data, logic, detailed specifications
- **Hates**: Vague claims, pressure, emotional appeals
- **Test phrases that work**: "The data shows..." / "Let me explain the technology..."
- **Test phrases that fail**: "Just trust me" / "Everyone loves it"

---

## Framework Testing

### LERA Framework (Price Objection)
When customer says "It's too expensive":

| Step | Your Response |
|------|---------------|
| **L**isten | "I hear you, price is definitely a consideration..." |
| **E**mpathize | "I completely understand - it's a significant investment..." |
| **R**espond | "When you factor in the 15-year warranty and improved sleep quality..." |
| **A**sk | "Does that help address your concern about the price?" |

### CECAP Framework (Emotional Objection)
When customer says "I need to think about it":

| Step | Your Response |
|------|---------------|
| **C**larify | "Of course! What specifically would you like to think about?" |
| **E**mpathize | "I totally get it - this is an important decision..." |
| **C**heck | "So it sounds like you want to discuss with your partner?" |
| **A**ddress | "What if we scheduled a time for both of you to come in?" |
| **P**roceed | "Would Saturday afternoon work for you both?" |

### 3T's Close
When ready to close:

| Step | Your Response |
|------|---------------|
| **T**oday | "If you decide today, you'll start sleeping better this week..." |
| **T**omorrow | "Waiting means another week of poor sleep..." |
| **T**ogether | "Let's get this set up for you - I'll walk you through everything..." |

---

## Checking Your Results

### During Session
- **Progress Bar**: Shows current PULSE stage (1-5)
- **Sentiment Gauge**: Shows customer trust level (overlaid on avatar)
- **Chat History**: Review your conversation

### After Session (Feedback Page)
- **Overall Score**: Percentage (≥70% = PASS)
- **Sale Outcome**: WON ✅ or LOST ❌
- **Rubric Breakdown**:
  - BCE (Behavioral Compliance): 40% weight
  - MCF (Methodology Fidelity): 35% weight
  - CPO (Conversion Outcome): 25% weight
- **Missteps Detected**: List of trust-damaging behaviors

---

## Quick Reference: Pass vs Fail

| Aspect | PASS ✅ | FAIL ❌ |
|--------|---------|---------|
| Trust Score | ≥7 at end | ≤3 or dropped to 0 |
| PULSE Stages | Reached Stage 4-5 | Stuck at Stage 1-2 |
| Sale Outcome | WON | LOST or STALLED |
| Overall Score | ≥70% | <70% |
| Missteps | 0-1 minor | 3+ or critical |

---

## Environment Variables (Dev Mode)

For testing with a consistent session ID:

```bash
NEXT_PUBLIC_USE_DEV_SESSION=true
NEXT_PUBLIC_DEV_SESSION_ID=dev-test-session-001
ALLOW_TEST_SEED=true
```

---

## URLs

| Page | URL | Purpose |
|------|-----|---------|
| Login | `/` | Demo login (demo/demo) |
| Pre-Session | `/pre-session` | Select persona, start session |
| Session | `/session` | Active training conversation |
| Feedback | `/feedback` | View scores and results |
| Admin | `/admin` | Manage prompts/agents |
| Admin Overview | `/admin/overview` | View all AI components |

---

*Last updated: December 2024*
