import json
import logging
import os
from typing import Any, Dict

import azure.functions as func
import requests

from shared_code.blob import write_json, now_iso
from shared_code.http import json_ok, no_content, text_error

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
}


def _ok(body: Any, status: int = 200) -> func.HttpResponse:
    return json_ok(body, status=status, headers=CORS_HEADERS)


def _no_content() -> func.HttpResponse:
    return no_content(headers=CORS_HEADERS)


def _error(msg: str, status: int) -> func.HttpResponse:
    return text_error(msg, status=status, headers=CORS_HEADERS)


PULSE_TRAINER_SYSTEM_PROMPT = """You are the PULSE Training Coach.

Your role is to train a sales learner on the PULSE Selling framework:

- Probe – Open the conversation, build rapport, and ask smart, open-ended questions that reveal context.
- Understand – Uncover true needs, constraints, and emotions. Reflect back what you heard and confirm understanding.
- Link – Connect recommendations directly to the customer’s stated needs, using their language.
- Simplify – Reduce friction and confusion by narrowing choices, explaining trade-offs, and addressing common objections.
- Earn – Make a professional recommendation and earn a clear commitment: a decision, a scheduled follow-up, or the next concrete step.

You will be given a CONFIG object and a SESSION object as JSON. Use them to understand:
- Which PULSE step is being trained (pulse_step).
- The scenario context and rubric (success_criteria and common_errors).
- The learner's latest answer and any prior history in this session.

Behave according to the CONFIG flags:
- If adaptive_trainer.enabled is false, you should only perform a static evaluation and must NOT ask follow-up questions.
- If adaptive_trainer.enabled is true, you should run an adaptive training loop:
  - Diagnose where the learner is strong vs weak for the current PULSE step.
  - Ask clear, focused follow-up questions to deepen understanding on THIS step.
  - Only consider advancing once mastery is likely.
- If adaptive_trainer.self_annealing_enabled is true, in addition to the above you should emit trainer_change_log suggestions based on patterns you see.

Always return a single JSON object with this exact top-level shape (no extra keys):
{
  "mode": "ask_followup" | "advance_step" | "end_session" | "static_evaluation",
  "diagnosis": {
    "understanding_level": "strong" | "developing" | "weak",
    "primary_error_type": "none" | "missing_depth" | "off_target" | "vague" | "mechanical" | "other",
    "brief_explanation": "string"
  },
  "next_question": {
    "text": "string or null",
    "purpose": "string",
    "difficulty": "basic" | "intermediate" | "advanced"
  },
  "micro_fortification": {
    "enabled": true | false,
    "summary_to_learner": "string",
    "quick_check_question": "string"
  },
  "mastery_estimate": {
    "pulse_step": "Probe" | "Understand" | "Link" | "Simplify" | "Earn",
    "status": "not_started" | "weak" | "developing" | "solid" | "mastery_likely",
    "evidence": ["string"]
  },
  "trainer_change_log": {
    "emit": true | false,
    "observed_pattern": "string",
    "suspected_root_cause": "string",
    "proposed_rubric_changes": ["string"],
    "proposed_prompt_changes": ["string"],
    "proposed_scenario_changes": ["string"],
    "examples_and_tips_for_trainers": ["string"]
  }
}

Respond with STRICT JSON only. Do not include Markdown, comments, or any text outside the JSON object."""


def _call_openai_trainer(config: Dict[str, Any], session: Dict[str, Any]) -> Dict[str, Any]:
    """Call Azure OpenAI chat completion for the PULSE Trainer.

    Expects environment variables:
      - OPENAI_ENDPOINT
      - OPENAI_API_VERSION
      - AZURE_OPENAI_API_KEY
      - OPENAI_DEPLOYMENT_PERSONA_HIGH_REASONING or OPENAI_DEPLOYMENT_PERSONA_CORE_CHAT
    """

    endpoint = os.getenv("OPENAI_ENDPOINT", "").rstrip("/")
    api_version = os.getenv("OPENAI_API_VERSION", "")
    api_key = os.getenv("AZURE_OPENAI_API_KEY", "")
    deployment = (
        os.getenv("OPENAI_DEPLOYMENT_PERSONA_HIGH_REASONING")
        or os.getenv("OPENAI_DEPLOYMENT_PERSONA_CORE_CHAT")
        or ""
    )

    if not endpoint or not api_version or not api_key or not deployment:
        raise RuntimeError("Missing Azure OpenAI configuration for trainer_pulse_step")

    url = f"{endpoint}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"

    messages = [
        {"role": "system", "content": PULSE_TRAINER_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": json.dumps({"CONFIG": config, "SESSION": session}, ensure_ascii=False),
        },
    ]

    payload: Dict[str, Any] = {
        "messages": messages,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }

    headers = {
        "Content-Type": "application/json",
        "api-key": api_key,
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()

    data = resp.json()
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("No choices returned from Azure OpenAI")

    message = choices[0].get("message") or {}
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("Empty content from Azure OpenAI")

    return json.loads(content)


def _maybe_log_trainer_change(config: Dict[str, Any], session: Dict[str, Any], output: Dict[str, Any]) -> None:
    """Persist trainer_change_log when emit=True as a self-annealing signal.

    Logs are written to the same blob container used for prompts under a
    dedicated prefix so they can be reviewed offline without impacting
    runtime behavior. Any errors are swallowed to avoid breaking training
    flows.
    """

    try:
        tcl = output.get("trainer_change_log") or {}
        if not isinstance(tcl, dict) or not tcl.get("emit"):
            return

        pulse_step = str(session.get("pulse_step") or "Unknown")
        scenario = session.get("scenario") or {}
        scenario_id = str(scenario.get("id") or "unknown-scenario")
        learner_id = str(session.get("learner_id") or "unknown-learner")
        session_id = str(session.get("session_id") or "unknown-session")

        date = now_iso().split("T", 1)[0]
        path = f"trainer-change-logs/{date}/{pulse_step}/{scenario_id}/{session_id}.json"

        payload: Dict[str, Any] = {
            "timestamp": now_iso(),
            "pulse_step": pulse_step,
            "scenario_id": scenario_id,
            "learner_id": learner_id,
            "session_id": session_id,
            "config": config,
            "trainer_change_log": tcl,
        }

        write_json(path, payload)
    except Exception as log_exc:  # noqa: BLE001
        logging.exception("trainer_pulse_step logging failed: %s", log_exc)


def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("trainer_pulse_step request: %s", req.method)

    if req.method == "OPTIONS":
        return _no_content()

    if req.method != "POST":
        return _error("Method not allowed", 405)

    try:
        body: Dict[str, Any] = req.get_json()
    except Exception:
        return _error("Invalid JSON", 400)

    config = body.get("config") or {}
    session = body.get("session") or {}

    pulse_step = session.get("pulse_step") or "Probe"
    latest_answer = (session.get("latest_answer") or {}).get("learner_answer") or ""

    trainer_enabled_env = os.getenv("PULSE_TRAINER_ENABLED", "false").strip().lower()
    trainer_enabled = trainer_enabled_env in ("true", "1", "yes")
    if not trainer_enabled:
        output = {
            "mode": "static_evaluation",
            "diagnosis": {
                "understanding_level": "developing",
                "primary_error_type": "other",
                "brief_explanation": "PULSE Trainer is disabled in this environment. Enable PULSE_TRAINER_ENABLED to use adaptive training.",
            },
            "next_question": {
                "text": None,
                "purpose": "",
                "difficulty": "basic",
            },
            "micro_fortification": {
                "enabled": False,
                "summary_to_learner": "",
                "quick_check_question": "",
            },
            "mastery_estimate": {
                "pulse_step": pulse_step,
                "status": "not_started",
                "evidence": [],
            },
            "trainer_change_log": {
                "emit": False,
                "observed_pattern": "",
                "suspected_root_cause": "",
                "proposed_rubric_changes": [],
                "proposed_prompt_changes": [],
                "proposed_scenario_changes": [],
                "examples_and_tips_for_trainers": [],
            },
        }
        return _ok(output)

    adaptive = config.get("adaptive_trainer") or {} if isinstance(config, dict) else {}
    adaptive_enabled = bool(adaptive.get("enabled"))
    self_annealing_enabled = bool(adaptive.get("self_annealing_enabled"))

    if not adaptive_enabled:
        output = {
            "mode": "static_evaluation",
            "diagnosis": {
                "understanding_level": "developing",
                "primary_error_type": "other",
                "brief_explanation": "Static evaluation: adaptive trainer is disabled in this environment.",
            },
            "next_question": {
                "text": None,
                "purpose": "",
                "difficulty": "basic",
            },
            "micro_fortification": {
                "enabled": False,
                "summary_to_learner": "",
                "quick_check_question": "",
            },
            "mastery_estimate": {
                "pulse_step": pulse_step,
                "status": "not_started",
                "evidence": [],
            },
            "trainer_change_log": {
                "emit": False,
                "observed_pattern": "",
                "suspected_root_cause": "",
                "proposed_rubric_changes": [],
                "proposed_prompt_changes": [],
                "proposed_scenario_changes": [],
                "examples_and_tips_for_trainers": [],
            },
        }
        return _ok(output)

    try:
        llm_output = _call_openai_trainer(config, session)
        if not isinstance(llm_output, dict):
            raise RuntimeError("Trainer LLM output was not a JSON object")
        _maybe_log_trainer_change(config, session, llm_output)
        return _ok(llm_output)
    except Exception as exc:  # noqa: BLE001
        logging.exception("trainer_pulse_step LLM call failed: %s", exc)

        fallback = {
            "mode": "ask_followup",
            "diagnosis": {
                "understanding_level": "developing" if latest_answer else "weak",
                "primary_error_type": "missing_depth",
                "brief_explanation": "Fallback stub: unable to reach trainer model; treating this as a practice turn on the current PULSE step.",
            },
            "next_question": {
                "text": "What is one additional thing you would ask or say to improve your response for this step?",
                "purpose": "Encourage the learner to deepen their answer on the current PULSE step.",
                "difficulty": "basic",
            },
            "micro_fortification": {
                "enabled": False,
                "summary_to_learner": "",
                "quick_check_question": "",
            },
            "mastery_estimate": {
                "pulse_step": pulse_step,
                "status": "developing",
                "evidence": [
                    "Fallback stub: mastery will be estimated by the full LLM-powered trainer when available.",
                ],
            },
            "trainer_change_log": {
                "emit": False,
                "observed_pattern": "",
                "suspected_root_cause": "",
                "proposed_rubric_changes": [],
                "proposed_prompt_changes": [],
                "proposed_scenario_changes": [],
                "examples_and_tips_for_trainers": [],
            },
        }
        return _ok(fallback)
