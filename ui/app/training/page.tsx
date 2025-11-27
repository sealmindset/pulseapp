"use client";

import { useState } from "react";

const ENABLE_TRAINING =
  process.env.NEXT_PUBLIC_ENABLE_TRAINING === "true" &&
  process.env.NEXT_PUBLIC_ENV_NAME !== "prod";

const defaultScenario = {
  id: "pulse-basic-1",
  title: "Customer asks about upgrading their phone plan",
  description:
    "A customer walks into the store asking about upgrading their phone plan but has not shared any details about how they use their phone today.",
  complexity_level: "basic",
};

const PULSE_STEPS = ["Probe", "Understand", "Link", "Simplify", "Earn"] as const;
type PulseStep = (typeof PULSE_STEPS)[number];

const rubricsByStep: Record<
  PulseStep,
  { pulse_step: PulseStep; success_criteria: string[]; common_errors: string[] }
> = {
  Probe: {
    pulse_step: "Probe",
    success_criteria: [
      "Asks 2–3 open-ended questions to understand context and goals before recommending anything.",
      "Avoids jumping straight into pitching a specific product or plan.",
    ],
    common_errors: [
      "Immediately recommending a specific plan without asking questions.",
      "Asking only yes/no questions that do not reveal much context.",
    ],
  },
  Understand: {
    pulse_step: "Understand",
    success_criteria: [
      "Reflects back what the customer said in their own words to confirm understanding.",
      "Surfaces needs, constraints, and emotions rather than only restating facts.",
    ],
    common_errors: [
      "Moves on without confirming understanding or asking follow-up questions.",
      "Focuses only on features and usage, ignoring emotions or constraints.",
    ],
  },
  Link: {
    pulse_step: "Link",
    success_criteria: [
      "Explicitly links each recommendation to something the customer said they care about.",
      "Uses the customer’s language to describe how the solution fits their situation.",
    ],
    common_errors: [
      "Describes product features without tying them back to stated needs.",
      "Uses generic benefit language that could apply to anyone.",
    ],
  },
  Simplify: {
    pulse_step: "Simplify",
    success_criteria: [
      "Narrows options to a small set that clearly fits the customer’s situation.",
      "Explains trade-offs in plain language without jargon.",
    ],
    common_errors: [
      "Presents too many options at once, overwhelming the customer.",
      "Uses technical or pricing jargon without clarifying what it means for the customer.",
    ],
  },
  Earn: {
    pulse_step: "Earn",
    success_criteria: [
      "Makes a clear recommendation based on everything learned in the conversation.",
      "Asks for a concrete next step (decision today, follow-up time, or similar).",
    ],
    common_errors: [
      "Ends the conversation without recommending a next step.",
      "Uses pushy language that ignores what the customer shared.",
    ],
  },
};

function getInitialQuestion(step: PulseStep): string {
  switch (step) {
    case "Understand":
      return "After the customer answers your first question, what follow-up would you ask to understand their situation more deeply?";
    case "Link":
      return "How would you link a recommendation to what the customer told you, using their own words?";
    case "Simplify":
      return "How would you simplify the options so the customer does not feel overwhelmed?";
    case "Earn":
      return "What would you say to professionally recommend a next step and earn a clear commitment?";
    case "Probe":
    default:
      return "In this scenario, what is the first open-ended question you would ask the customer?";
  }
}

export default function TrainingPage() {
  const [pulseStep, setPulseStep] = useState<PulseStep>("Probe");
  const [question, setQuestion] = useState(getInitialQuestion("Probe"));
  const [answer, setAnswer] = useState("");
  const [history, setHistory] = useState<any[]>([]);
  const [output, setOutput] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    setError(null);
    if (!answer.trim()) {
      setError("Please enter an answer before submitting.");
      return;
    }
    setLoading(true);
    try {
      const body = {
        config: {
          adaptive_trainer: {
            enabled: true,
            self_annealing_enabled: false,
          },
        },
        session: {
          learner_id: "demo-learner",
          session_id: "demo-session",
          pulse_step: pulseStep,
          scenario: defaultScenario,
          rubric: rubricsByStep[pulseStep],
          history,
          latest_answer: {
            question,
            learner_answer: answer,
          },
          aggregated_pattern_hints: [],
        },
      };

      const res = await fetch("/api/orchestrator/trainer/pulse/step", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        throw new Error(`Trainer request failed (${res.status})`);
      }

      const data = await res.json();
      setOutput(data);
      setHistory((prev) => [
        ...prev,
        {
          turn_index: prev.length,
          question,
          learner_answer: answer,
        },
      ]);

      if (data?.next_question?.text) {
        setQuestion(data.next_question.text);
      }
      setAnswer("");
    } catch (e: any) {
      setError(e.message || "Trainer request failed");
    } finally {
      setLoading(false);
    }
  };

  const mastery = output?.mastery_estimate;
  const rubric = rubricsByStep[pulseStep];

  if (!ENABLE_TRAINING) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold">PULSE Training</h1>
        <p className="text-sm text-gray-600">
          Training is disabled in this environment. To enable in dev, set NEXT_PUBLIC_ENABLE_TRAINING=true and
          NEXT_PUBLIC_ENV_NAME!=prod.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">PULSE Training (Phase A/B Stub)</h1>
      <p className="text-sm text-gray-600">
        This page exercises the PULSE Trainer Agent endpoint with a fixed Probe scenario and stubbed backend logic.
      </p>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 space-y-4">
          <div className="space-y-3 rounded border border-gray-200 p-4">
            <div className="text-sm font-medium">Scenario</div>
            <div className="text-sm text-gray-700 font-semibold">{defaultScenario.title}</div>
            <div className="text-sm text-gray-700">{defaultScenario.description}</div>
            <div className="text-xs text-gray-500">Focus step: {pulseStep}</div>
            <div className="mt-2 flex flex-wrap gap-2 text-xs">
              {PULSE_STEPS.map((step) => (
                <button
                  key={step}
                  type="button"
                  onClick={() => {
                    setPulseStep(step);
                    setQuestion(getInitialQuestion(step));
                    setOutput(null);
                    setHistory([]);
                    setError(null);
                  }}
                  className={`rounded-full border px-3 py-1 ${
                    step === pulseStep
                      ? "border-black bg-black text-white"
                      : "border-gray-300 bg-white text-gray-800 hover:bg-gray-50"
                  }`}
                >
                  {step}
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-3 rounded border border-gray-200 p-4">
            <div className="text-sm font-medium">Trainer Question</div>
            <div className="text-sm text-gray-700">{question}</div>
            <textarea
              className="mt-2 w-full rounded border border-gray-300 p-2 text-sm"
              rows={4}
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              placeholder="Type what you would say to the customer..."
            />
            {error && <div className="rounded border border-red-200 bg-red-50 p-2 text-sm text-red-700">{error}</div>}
            <button
              onClick={submit}
              disabled={loading}
              className="inline-flex items-center rounded-md bg-black px-4 py-2 text-sm font-medium text-white hover:bg-gray-800 disabled:opacity-60"
            >
              {loading ? "Submitting..." : "Submit Answer"}
            </button>
          </div>
        </div>

        <div className="space-y-4">
          <div className="space-y-2 rounded border border-gray-200 p-4">
            <div className="text-sm font-medium">Rubric — {pulseStep}</div>
            <div className="text-xs text-gray-500">What a strong {pulseStep} answer should and should not do.</div>
            <div className="mt-2 text-xs font-semibold text-gray-600">Success criteria</div>
            <ul className="list-disc pl-5 text-sm text-gray-700">
              {rubric.success_criteria.map((line, idx) => (
                <li key={idx}>{line}</li>
              ))}
            </ul>
            <div className="mt-2 text-xs font-semibold text-gray-600">Common errors</div>
            <ul className="list-disc pl-5 text-sm text-gray-700">
              {rubric.common_errors.map((line, idx) => (
                <li key={idx}>{line}</li>
              ))}
            </ul>
          </div>

          <div className="space-y-2 rounded border border-gray-200 p-4">
            <div className="text-sm font-medium">Trainer Feedback (Stub)</div>
            <div className="text-sm text-gray-700">
              {output?.diagnosis?.brief_explanation || "Submit an answer to see trainer feedback."}
            </div>
            {output?.next_question?.text && (
              <div className="text-sm text-gray-700">
                <span className="font-medium">Next question:</span> {output.next_question.text}
              </div>
            )}
          </div>

          <div className="space-y-1 rounded border border-gray-200 p-4">
            <div className="text-sm font-medium">Mastery Status (Stub)</div>
            <div className="text-sm text-gray-700">
              {mastery?.status ? `Status: ${mastery.status}` : "Status: not started"}
            </div>
            {Array.isArray(mastery?.evidence) && mastery.evidence.length > 0 && (
              <ul className="mt-1 list-disc pl-5 text-xs text-gray-600">
                {mastery.evidence.map((e: string, idx: number) => (
                  <li key={idx}>{e}</li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>

      {history.length > 0 && (
        <div className="space-y-2 rounded border border-gray-200 p-4">
          <div className="text-sm font-medium">Turn History (This Session)</div>
          <ul className="space-y-1 text-sm text-gray-700">
            {history.map((h, idx) => (
              <li key={idx}>
                <span className="font-semibold">Q{idx + 1}:</span> {h.question}
                <br />
                <span className="font-semibold">A{idx + 1}:</span> {h.learner_answer}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

