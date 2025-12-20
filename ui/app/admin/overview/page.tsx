"use client";

import { useState } from "react";

// ============================================================================
// PERSONAS - Customer behavior styles based on the Platinum Rule
// ============================================================================
const PERSONAS = [
  {
    id: "director",
    name: "Director",
    difficulty: "Expert/High Pressure",
    description: "Direct, results-oriented, impatient, values efficiency and bottom-line results",
    avatar: {
      character: "lisa",
      style: "casual-sitting",
      voice: "en-US-JennyNeural",
      voiceStyle: "customerservice",
    },
    introText: "Hello. I'm here to look at your products. Let's get started.",
    systemPromptSummary: "High-pressure customer who demands efficiency and facts. Tests trainee's ability to be brief and assertive.",
    color: "red",
  },
  {
    id: "relater",
    name: "Relater",
    difficulty: "Beginner/Empathy Focused",
    description: "Warm, patient, relationship-focused, values trust and personal connection",
    avatar: {
      character: "lisa",
      style: "casual-sitting",
      voice: "en-US-SaraNeural",
      voiceStyle: "friendly",
    },
    introText: "Hi there! I've been thinking about making a purchase and wanted to chat.",
    systemPromptSummary: "Hesitant customer who needs trust and empathy. Tests trainee's ability to build rapport and show patience.",
    color: "green",
  },
  {
    id: "socializer",
    name: "Socializer",
    difficulty: "Moderate/Enthusiasm Focused",
    description: "Enthusiastic, talkative, optimistic, values recognition and social interaction",
    avatar: {
      character: "lisa",
      style: "casual-sitting",
      voice: "en-US-AriaNeural",
      voiceStyle: "cheerful",
    },
    introText: "Hey! I'm so excited to be here! I've heard great things about you!",
    systemPromptSummary: "Energetic customer who gets easily distracted. Tests trainee's ability to maintain focus and enthusiasm.",
    color: "yellow",
  },
  {
    id: "thinker",
    name: "Thinker",
    difficulty: "Challenging/Logic Focused",
    description: "Analytical, detail-oriented, cautious, values accuracy and logical reasoning",
    avatar: {
      character: "lisa",
      style: "casual-sitting",
      voice: "en-US-MichelleNeural",
      voiceStyle: "calm",
    },
    introText: "Good afternoon. I've done some research and have a few questions.",
    systemPromptSummary: "Analytical customer who scrutinizes every claim. Tests trainee's product knowledge and logical reasoning.",
    color: "blue",
  },
];

// ============================================================================
// AGENTS - Evaluation agents for scoring trainee performance
// ============================================================================
const AGENTS = [
  {
    id: "orchestrator",
    name: "Chief Behavioral Certification Lead",
    type: "orchestrator",
    description: "Primary agent that manages evaluation workflow and compiles the final Behavioral Certification Score",
    weight: null,
    responsibilities: [
      "Distribute transcript to all sub-agents",
      "Aggregate scores and feedback",
      "Calculate weighted average (BCE 40%, MCF 35%, CPO 25%)",
      "Determine pass/fail based on 85% threshold",
    ],
  },
  {
    id: "bce",
    name: "Behavioral Compliance Evaluator (BCE)",
    type: "evaluator",
    description: "Scores trainee's mastery of the Platinum Rule and emotional engagement",
    weight: 0.40,
    focusArea: "Step 1: Connect & Discover",
    scoringCriteria: [
      { name: "Platinum Rule Adaptation", points: 40 },
      { name: "Empathy and Trust Building", points: 30 },
      { name: "CECAP/LERA Emotional Application", points: 30 },
    ],
  },
  {
    id: "mcf",
    name: "Methodology & Content Fidelity Checker (MCF)",
    type: "evaluator",
    description: "Verifies mandatory execution of PULSE steps and communication tools",
    weight: 0.35,
    focusArea: "PULSE Steps 1-4",
    scoringCriteria: [
      { name: "Discovery Capture", points: 30 },
      { name: "Mini-Talk/Chunking", points: 30 },
      { name: "Accessory Integration", points: 25 },
      { name: "Closing Foundation", points: 15 },
    ],
  },
  {
    id: "cpo",
    name: "Conversion & Psychological Outcome Assessor (CPO)",
    type: "evaluator",
    description: "Assesses deployment of psychological levers to drive conversion",
    weight: 0.25,
    focusArea: "Step 4: Address Concerns & Close Today",
    scoringCriteria: [
      { name: "Urgency & FOMO", points: 30 },
      { name: "Closing Framework", points: 35 },
      { name: "Handling Financial Tension", points: 25 },
      { name: "Ownership Language", points: 10 },
    ],
  },
];

// ============================================================================
// PROMPTS - System prompts used throughout the platform
// ============================================================================
const PROMPTS = [
  {
    id: "pulse-customer-persona",
    title: "PULSE Customer Persona",
    type: "system",
    description: "Base system prompt for AI customer in sales training simulation",
    usedBy: "Chat endpoint - persona conversations",
  },
  {
    id: "pulse-evaluator",
    title: "PULSE Evaluator Orchestrator",
    type: "system",
    description: "System prompt for the evaluation orchestrator agent",
    usedBy: "Feedback endpoint - session scoring",
  },
  {
    id: "pulse-stage-detector",
    title: "PULSE Stage Detector",
    type: "system",
    description: "Detects which PULSE stage (1-5) the conversation is in",
    usedBy: "Chat endpoint - stage progression",
  },
  {
    id: "misstep-detector",
    title: "Misstep Detector",
    type: "system",
    description: "Detects critical sales missteps that can cause sale loss",
    usedBy: "Chat endpoint - trust tracking",
  },
  {
    id: "emotion-analyzer",
    title: "Emotion Analyzer",
    type: "system",
    description: "Analyzes customer emotion for avatar expression",
    usedBy: "Chat endpoint - avatar emotions",
  },
];

// ============================================================================
// PULSE STAGES - The 5-step PULSE selling methodology
// ============================================================================
const PULSE_STAGES = [
  {
    stage: 1,
    name: "Probe",
    description: "Initial greeting, building rapport, discovering customer needs",
    keyBehaviors: ["Greeting", "Open-ended questions", "Active listening"],
  },
  {
    stage: 2,
    name: "Understand",
    description: "Deep dive into customer's situation, pain points, emotional reasons",
    keyBehaviors: ["Empathy", "Paraphrasing", "Identifying hot buttons"],
  },
  {
    stage: 3,
    name: "Link",
    description: "Connecting product features to customer's specific needs",
    keyBehaviors: ["Feature-benefit linking", "Mini-talks", "Ownership language"],
  },
  {
    stage: 4,
    name: "Solve",
    description: "Presenting solutions, handling objections, demonstrating value",
    keyBehaviors: ["Objection handling (LERA)", "Financing options", "Value building"],
  },
  {
    stage: 5,
    name: "Earn",
    description: "Closing the sale, asking for commitment, finalizing the purchase",
    keyBehaviors: ["Assumptive close", "Professional recommendation", "3T's close"],
  },
];

type TabType = "personas" | "agents" | "prompts" | "stages";

export default function AdminOverviewPage() {
  const [activeTab, setActiveTab] = useState<TabType>("personas");

  const tabs: { id: TabType; label: string; count: number }[] = [
    { id: "personas", label: "Personas", count: PERSONAS.length },
    { id: "agents", label: "Agents", count: AGENTS.length },
    { id: "prompts", label: "Prompts", count: PROMPTS.length },
    { id: "stages", label: "PULSE Stages", count: PULSE_STAGES.length },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">AI Components Overview</h1>
        <p className="text-sm text-gray-600 mt-1">
          All prompts, agents, and personas used in the PULSE sales training simulator
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-gray-200 pb-2">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2 rounded-t-lg text-sm font-medium transition-colors ${
              activeTab === tab.id
                ? "bg-black text-white"
                : "bg-gray-100 text-gray-700 hover:bg-gray-200"
            }`}
          >
            {tab.label}
            <span className="ml-2 px-2 py-0.5 rounded-full text-xs bg-white/20">
              {tab.count}
            </span>
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="space-y-4">
        {activeTab === "personas" && (
          <div className="grid gap-4 md:grid-cols-2">
            {PERSONAS.map((persona) => (
              <div
                key={persona.id}
                className={`rounded-lg border-2 p-4 ${
                  persona.color === "red" ? "border-red-200 bg-red-50" :
                  persona.color === "green" ? "border-green-200 bg-green-50" :
                  persona.color === "yellow" ? "border-yellow-200 bg-yellow-50" :
                  "border-blue-200 bg-blue-50"
                }`}
              >
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="text-lg font-semibold">{persona.name}</h3>
                    <span className="text-xs px-2 py-0.5 rounded-full bg-white/50">
                      {persona.difficulty}
                    </span>
                  </div>
                  <div className="text-2xl">
                    {persona.id === "director" && "👔"}
                    {persona.id === "relater" && "🤝"}
                    {persona.id === "socializer" && "🎉"}
                    {persona.id === "thinker" && "🔬"}
                  </div>
                </div>
                <p className="mt-2 text-sm text-gray-700">{persona.description}</p>
                <div className="mt-3 p-2 bg-white/50 rounded text-sm">
                  <div className="font-medium text-gray-600">System Prompt Summary:</div>
                  <div className="text-gray-700">{persona.systemPromptSummary}</div>
                </div>
                <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                  <div className="p-2 bg-white/50 rounded">
                    <div className="font-medium text-gray-600">Avatar</div>
                    <div>{persona.avatar.character} / {persona.avatar.style}</div>
                  </div>
                  <div className="p-2 bg-white/50 rounded">
                    <div className="font-medium text-gray-600">Voice</div>
                    <div>{persona.avatar.voice.replace("en-US-", "").replace("Neural", "")}</div>
                  </div>
                </div>
                <div className="mt-2 p-2 bg-white/50 rounded text-xs italic">
                  &ldquo;{persona.introText}&rdquo;
                </div>
              </div>
            ))}
          </div>
        )}

        {activeTab === "agents" && (
          <div className="space-y-4">
            <div className="p-4 bg-gray-50 rounded-lg border border-gray-200">
              <h3 className="font-semibold">Scoring Weights</h3>
              <div className="mt-2 flex gap-4">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full bg-blue-500"></div>
                  <span className="text-sm">BCE: 40%</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full bg-green-500"></div>
                  <span className="text-sm">MCF: 35%</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full bg-purple-500"></div>
                  <span className="text-sm">CPO: 25%</span>
                </div>
              </div>
              <div className="mt-2 text-sm text-gray-600">
                Passing threshold: <span className="font-semibold">85%</span>
              </div>
            </div>

            {AGENTS.map((agent) => (
              <div
                key={agent.id}
                className={`rounded-lg border p-4 ${
                  agent.type === "orchestrator" ? "border-gray-300 bg-gray-50" :
                  agent.id === "bce" ? "border-blue-200 bg-blue-50" :
                  agent.id === "mcf" ? "border-green-200 bg-green-50" :
                  "border-purple-200 bg-purple-50"
                }`}
              >
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="font-semibold">{agent.name}</h3>
                    <span className="text-xs px-2 py-0.5 rounded-full bg-white/50 uppercase">
                      {agent.type}
                    </span>
                    {agent.weight && (
                      <span className="ml-2 text-xs px-2 py-0.5 rounded-full bg-black text-white">
                        {(agent.weight * 100).toFixed(0)}% weight
                      </span>
                    )}
                  </div>
                </div>
                <p className="mt-2 text-sm text-gray-700">{agent.description}</p>
                
                {agent.focusArea && (
                  <div className="mt-2 text-sm">
                    <span className="font-medium">Focus Area:</span> {agent.focusArea}
                  </div>
                )}

                {agent.responsibilities && (
                  <div className="mt-3">
                    <div className="text-sm font-medium text-gray-600">Responsibilities:</div>
                    <ul className="mt-1 text-sm list-disc list-inside text-gray-700">
                      {agent.responsibilities.map((r, i) => (
                        <li key={i}>{r}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {agent.scoringCriteria && (
                  <div className="mt-3">
                    <div className="text-sm font-medium text-gray-600">Scoring Criteria:</div>
                    <div className="mt-1 grid gap-1">
                      {agent.scoringCriteria.map((c, i) => (
                        <div key={i} className="flex justify-between text-sm bg-white/50 px-2 py-1 rounded">
                          <span>{c.name}</span>
                          <span className="font-medium">{c.points} pts</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {activeTab === "prompts" && (
          <div className="space-y-3">
            {PROMPTS.map((prompt) => (
              <div
                key={prompt.id}
                className="rounded-lg border border-gray-200 p-4 bg-white"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="font-semibold">{prompt.title}</h3>
                    <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 uppercase">
                      {prompt.type}
                    </span>
                  </div>
                  <code className="text-xs bg-gray-100 px-2 py-1 rounded">{prompt.id}</code>
                </div>
                <p className="mt-2 text-sm text-gray-700">{prompt.description}</p>
                <div className="mt-2 text-xs text-gray-500">
                  <span className="font-medium">Used by:</span> {prompt.usedBy}
                </div>
              </div>
            ))}
          </div>
        )}

        {activeTab === "stages" && (
          <div className="space-y-4">
            <div className="flex items-center gap-2 p-4 bg-gradient-to-r from-blue-50 to-purple-50 rounded-lg border border-blue-200">
              {PULSE_STAGES.map((stage, i) => (
                <div key={stage.stage} className="flex items-center">
                  <div className="flex flex-col items-center">
                    <div className="w-10 h-10 rounded-full bg-black text-white flex items-center justify-center font-bold">
                      {stage.stage}
                    </div>
                    <div className="text-xs font-medium mt-1">{stage.name}</div>
                  </div>
                  {i < PULSE_STAGES.length - 1 && (
                    <div className="w-8 h-0.5 bg-gray-300 mx-1"></div>
                  )}
                </div>
              ))}
            </div>

            {PULSE_STAGES.map((stage) => (
              <div
                key={stage.stage}
                className="rounded-lg border border-gray-200 p-4 bg-white"
              >
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-full bg-black text-white flex items-center justify-center font-bold text-sm">
                    {stage.stage}
                  </div>
                  <div>
                    <h3 className="font-semibold">{stage.name}</h3>
                  </div>
                </div>
                <p className="mt-2 text-sm text-gray-700">{stage.description}</p>
                <div className="mt-3">
                  <div className="text-sm font-medium text-gray-600">Key Behaviors:</div>
                  <div className="mt-1 flex flex-wrap gap-2">
                    {stage.keyBehaviors.map((behavior, i) => (
                      <span
                        key={i}
                        className="text-xs px-2 py-1 rounded-full bg-gray-100 text-gray-700"
                      >
                        {behavior}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
