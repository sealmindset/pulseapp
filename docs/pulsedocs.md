You are GPT-5.1 Thinking running inside Windsurf IDE.

## GOAL

Update the existing `README.md` and any relevant documentation files in this repo to describe the **PULSE Selling** framework, using the following section as the canonical content.

Wherever the old SBN/Selling by Numbers methodology is currently described as the core framework, replace or supersede it with this **PULSE Selling Framework** section.

---

## TARGET SECTION (INSERT/REPLACE)

Use this exact text (you may adjust heading level `##` → `###` if needed to fit the existing README structure, but keep the content intact):

```markdown
## PULSE Selling Framework

The AI Trainer is built around a conversational framework called **PULSE Selling**.

**PULSE** is a 5-step structure for high-quality customer conversations:

- **P – Probe**  
  Open the conversation, build quick rapport, and ask smart, open-ended questions that reveal context fast.

- **U – Understand**  
  Go beyond surface requests to uncover true needs, constraints, and emotions. Reflect back what you heard and verify you understood correctly.

- **L – Link**  
  Connect recommendations directly to what the customer said, using their language. Make it clear how each option maps to their specific goals and pains.

- **S – Simplify**  
  Reduce friction and confusion by narrowing choices, explaining trade-offs in plain language, and addressing common objections without overwhelming the customer.

- **E – Earn**  
  Make a professional recommendation based on everything you learned, then earn a clear commitment: a decision, a scheduled follow-up, or the next concrete step.

### How the Trainer uses PULSE

During each simulated conversation, the AI Coach evaluates the associate against the PULSE steps:

- Did they **Probe** with meaningful, open-ended questions?
- Did they **Understand** the customer’s real situation and emotions?
- Did they **Link** recommendations clearly to the customer’s words?
- Did they **Simplify** choices instead of overwhelming the customer?
- Did they **Earn** a committed next step?

After the session, the Trainer returns:

- A **score** for each PULSE step (e.g. 0–3)
- A brief **reason** for the score
- 1–2 **coaching tips** on how to improve that part of the conversation next time

This turns abstract “soft skills” into concrete, coachable behaviors while keeping the associate focused on a simple, memorable structure: **Probe → Understand → Link → Simplify → Earn**.

	1.	Locate the existing methodology section(s) in:
	•	README.md
	•	any top-level docs such as docs/*.md, aidocs/*.md, or similar
that currently describe SBN / Selling by Numbers as the core sales framework.
	2.	Update the README.md:
	•	If there is a dedicated section describing the old SBN methodology, replace that section with the PULSE section above.
	•	If SBN is mentioned inline without a clear section, insert the PULSE section in the most appropriate place (likely after the main overview of the Trainer) and adjust surrounding text to reference PULSE Selling instead of SBN.
	3.	Update other documentation files (Markdown only):
	•	For each doc that explains the methodology at a high level, either:
	•	Replace the SBN description with the PULSE section (or a trimmed version of it), OR
	•	Add a new “PULSE Selling Framework” section and update references so that PULSE is clearly the primary framework.
	•	Ensure the wording is consistent (PULSE Selling, Probe / Understand / Link / Simplify / Earn).
	4.	Preserve history where needed:
	•	If any doc must mention that the system was originally based on another methodology, you may keep a short historical note, e.g.:
	•	“The current system uses the PULSE Selling framework.”
	•	Do NOT copy or restate proprietary SBN content; PULSE should be presented as the active, canonical framework.
	5.	Style & consistency:
	•	Keep headings, spacing, and Markdown formatting consistent with the existing docs.
	•	Make sure all references to the framework now point to PULSE Selling.
	•	Check that internal links or TOC entries (if present) are updated to match the new section heading.

⸻

OUTPUT
	1.	List which files you modified (e.g., README.md, docs/trainer_overview.md, etc.).
	2.	For each file, briefly describe what changed (e.g., “Replaced SBN methodology description with PULSE section”, “Inserted new PULSE section and updated references”).
	3.	Show the updated README.md PULSE section so I can visually verify it.
