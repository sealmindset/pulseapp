"""
Admin overview endpoint - returns all prompts, agents, and personas used in the project.

This is a simple read-only endpoint that provides a comprehensive view of all
AI components used in the PULSE training platform.
"""

import logging
from typing import Any, Dict, List

import azure.functions as func

from shared_code.http import json_ok, no_content, text_error


CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
}


# ============================================================================
# PERSONAS - Customer behavior styles based on the Platinum Rule
# ============================================================================
PERSONAS = [
    {
        "id": "director",
        "name": "Director",
        "difficulty": "Expert/High Pressure",
        "description": "Direct, results-oriented, impatient, values efficiency and bottom-line results",
        "avatar": {
            "character": "lisa",
            "style": "casual-sitting",
            "voice": "en-US-JennyNeural",
            "voice_style": "customerservice",
        },
        "intro_text": "Hello. I'm here to look at your products. Let's get started.",
        "system_prompt_summary": "High-pressure customer who demands efficiency and facts. Tests trainee's ability to be brief and assertive.",
    },
    {
        "id": "relater",
        "name": "Relater",
        "difficulty": "Beginner/Empathy Focused",
        "description": "Warm, patient, relationship-focused, values trust and personal connection",
        "avatar": {
            "character": "lisa",
            "style": "casual-sitting",
            "voice": "en-US-SaraNeural",
            "voice_style": "friendly",
        },
        "intro_text": "Hi there! I've been thinking about making a purchase and wanted to chat.",
        "system_prompt_summary": "Hesitant customer who needs trust and empathy. Tests trainee's ability to build rapport and show patience.",
    },
    {
        "id": "socializer",
        "name": "Socializer",
        "difficulty": "Moderate/Enthusiasm Focused",
        "description": "Enthusiastic, talkative, optimistic, values recognition and social interaction",
        "avatar": {
            "character": "lisa",
            "style": "casual-sitting",
            "voice": "en-US-AriaNeural",
            "voice_style": "cheerful",
        },
        "intro_text": "Hey! I'm so excited to be here! I've heard great things about you!",
        "system_prompt_summary": "Energetic customer who gets easily distracted. Tests trainee's ability to maintain focus and enthusiasm.",
    },
    {
        "id": "thinker",
        "name": "Thinker",
        "difficulty": "Challenging/Logic Focused",
        "description": "Analytical, detail-oriented, cautious, values accuracy and logical reasoning",
        "avatar": {
            "character": "lisa",
            "style": "casual-sitting",
            "voice": "en-US-MichelleNeural",
            "voice_style": "calm",
        },
        "intro_text": "Good afternoon. I've done some research and have a few questions.",
        "system_prompt_summary": "Analytical customer who scrutinizes every claim. Tests trainee's product knowledge and logical reasoning.",
    },
]


# ============================================================================
# AGENTS - Evaluation agents for scoring trainee performance
# ============================================================================
AGENTS = [
    {
        "id": "orchestrator",
        "name": "Chief Behavioral Certification Lead",
        "type": "orchestrator",
        "description": "Primary agent that manages evaluation workflow and compiles the final Behavioral Certification Score",
        "weight": None,
        "responsibilities": [
            "Distribute transcript to all sub-agents",
            "Aggregate scores and feedback",
            "Calculate weighted average (BCE 40%, MCF 35%, CPO 25%)",
            "Determine pass/fail based on 85% threshold",
        ],
    },
    {
        "id": "bce",
        "name": "Behavioral Compliance Evaluator (BCE)",
        "type": "evaluator",
        "description": "Scores trainee's mastery of the Platinum Rule and emotional engagement",
        "weight": 0.40,
        "focus_area": "Step 1: Connect & Discover",
        "scoring_criteria": [
            {"name": "Platinum Rule Adaptation", "points": 40},
            {"name": "Empathy and Trust Building", "points": 30},
            {"name": "CECAP/LERA Emotional Application", "points": 30},
        ],
    },
    {
        "id": "mcf",
        "name": "Methodology & Content Fidelity Checker (MCF)",
        "type": "evaluator",
        "description": "Verifies mandatory execution of PULSE steps and communication tools",
        "weight": 0.35,
        "focus_area": "PULSE Steps 1-4",
        "scoring_criteria": [
            {"name": "Discovery Capture", "points": 30},
            {"name": "Mini-Talk/Chunking", "points": 30},
            {"name": "Accessory Integration", "points": 25},
            {"name": "Closing Foundation", "points": 15},
        ],
    },
    {
        "id": "cpo",
        "name": "Conversion & Psychological Outcome Assessor (CPO)",
        "type": "evaluator",
        "description": "Assesses deployment of psychological levers to drive conversion",
        "weight": 0.25,
        "focus_area": "Step 4: Address Concerns & Close Today",
        "scoring_criteria": [
            {"name": "Urgency & FOMO", "points": 30},
            {"name": "Closing Framework", "points": 35},
            {"name": "Handling Financial Tension", "points": 25},
            {"name": "Ownership Language", "points": 10},
        ],
    },
]


# ============================================================================
# PROMPTS - System prompts used throughout the platform
# ============================================================================
PROMPTS = [
    {
        "id": "pulse-customer-persona",
        "title": "PULSE Customer Persona",
        "type": "system",
        "description": "Base system prompt for AI customer in sales training simulation",
        "used_by": "Chat endpoint - persona conversations",
    },
    {
        "id": "pulse-evaluator",
        "title": "PULSE Evaluator Orchestrator",
        "type": "system",
        "description": "System prompt for the evaluation orchestrator agent",
        "used_by": "Feedback endpoint - session scoring",
    },
    {
        "id": "pulse-stage-detector",
        "title": "PULSE Stage Detector",
        "type": "system",
        "description": "Detects which PULSE stage (1-5) the conversation is in",
        "used_by": "Chat endpoint - stage progression",
    },
    {
        "id": "misstep-detector",
        "title": "Misstep Detector",
        "type": "system",
        "description": "Detects critical sales missteps that can cause sale loss",
        "used_by": "Chat endpoint - trust tracking",
    },
    {
        "id": "emotion-analyzer",
        "title": "Emotion Analyzer",
        "type": "system",
        "description": "Analyzes customer emotion for avatar expression",
        "used_by": "Chat endpoint - avatar emotions",
    },
]


# ============================================================================
# PULSE STAGES - The 5-step PULSE selling methodology
# ============================================================================
PULSE_STAGES = [
    {
        "stage": 1,
        "name": "Probe",
        "description": "Initial greeting, building rapport, discovering customer needs",
        "key_behaviors": ["Greeting", "Open-ended questions", "Active listening"],
    },
    {
        "stage": 2,
        "name": "Understand",
        "description": "Deep dive into customer's situation, pain points, emotional reasons",
        "key_behaviors": ["Empathy", "Paraphrasing", "Identifying hot buttons"],
    },
    {
        "stage": 3,
        "name": "Link",
        "description": "Connecting product features to customer's specific needs",
        "key_behaviors": ["Feature-benefit linking", "Mini-talks", "Ownership language"],
    },
    {
        "stage": 4,
        "name": "Solve",
        "description": "Presenting solutions, handling objections, demonstrating value",
        "key_behaviors": ["Objection handling (LERA)", "Financing options", "Value building"],
    },
    {
        "stage": 5,
        "name": "Earn",
        "description": "Closing the sale, asking for commitment, finalizing the purchase",
        "key_behaviors": ["Assumptive close", "Professional recommendation", "3T's close"],
    },
]


def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("admin_overview request: %s", req.method)

    if req.method == "OPTIONS":
        return no_content(headers=CORS_HEADERS)

    if req.method != "GET":
        return text_error("Method not allowed", 405, headers=CORS_HEADERS)

    response = {
        "title": "PULSE Training Platform - AI Components Overview",
        "description": "All prompts, agents, and personas used in the PULSE sales training simulator",
        "personas": {
            "description": "Customer behavior styles based on the Platinum Rule",
            "count": len(PERSONAS),
            "items": PERSONAS,
        },
        "agents": {
            "description": "Evaluation agents for scoring trainee performance",
            "count": len(AGENTS),
            "scoring_weights": {
                "BCE": "40%",
                "MCF": "35%",
                "CPO": "25%",
            },
            "passing_threshold": "85%",
            "items": AGENTS,
        },
        "prompts": {
            "description": "System prompts used throughout the platform",
            "count": len(PROMPTS),
            "items": PROMPTS,
        },
        "pulse_stages": {
            "description": "The 5-step PULSE selling methodology",
            "count": len(PULSE_STAGES),
            "items": PULSE_STAGES,
        },
    }

    return json_ok(response, headers=CORS_HEADERS)
