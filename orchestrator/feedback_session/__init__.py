import json
import logging
import os
from typing import Any, Dict, List

import azure.functions as func
import requests

from shared_code.blob import read_json
from shared_code.http import json_ok, no_content, text_error
from shared_code.analytics_events import record_session_scorecard_event
from shared_code.readiness_service import compute_and_store_user_readiness_for_session


CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
}


def _ok(body: Any, status: int = 200) -> func.HttpResponse:
    return json_ok(body, status=status, headers=CORS_HEADERS)


def _no_content() -> func.HttpResponse:
    return no_content(headers=CORS_HEADERS)


def _error(message: str, status: int) -> func.HttpResponse:
    return text_error(message, status=status, headers=CORS_HEADERS)


def _orchestrator_enabled() -> bool:
    value = os.getenv("TRAINING_ORCHESTRATOR_ENABLED", "false").strip().lower()
    return value in ("true", "1", "yes")


def _load_transcript(session_id: str) -> List[str]:
    path = f"sessions/{session_id}/transcript.json"
    doc = read_json(path) or {}
    tx = doc.get("transcript") if isinstance(doc, dict) else None
    if isinstance(tx, list):
        return [str(x) for x in tx]
    if isinstance(tx, str):
        return [tx]
    return []


def _load_scorecard(session_id: str) -> Dict[str, Any]:
    """Load an optional BCE/MCF/CPO scorecard for the session.

    The expected shape is a dictionary with optional keys:

      - overall: { "score": number, ... }
      - bce:     { "score": number, "passed"?: bool, "summary"?: str, ... }
      - mcf:     { "score": number, "passed"?: bool, "summary"?: str, ... }
      - cpo:     { "score": number, "passed"?: bool, "summary"?: str, ... }

    If no scorecard exists or it is malformed, an empty dict is returned and
    the feedback response will simply omit scoring fields.
    """

    path = f"sessions/{session_id}/scorecard.json"
    doc = read_json(path)
    return doc if isinstance(doc, dict) else {}


def _load_evaluator_prompt() -> str | None:
    """Load the PULSE evaluator system prompt from blob storage.

    Prompts are managed via the Admin UI and stored in the same container as
    other prompt content. We expect a document at `prompts/{id}.json` with a
    `content` field containing the system prompt markdown/text.
    """

    prompt_id = os.getenv("PULSE_EVALUATOR_PROMPT_ID", "pulse-evaluator-v1")
    path = f"prompts/{prompt_id}.json"
    doc = read_json(path)
    if not isinstance(doc, dict):
        logging.warning("feedback_session: evaluator prompt %s not found", prompt_id)
        return None
    content = doc.get("content")
    if not isinstance(content, str) or not content.strip():
        logging.warning("feedback_session: evaluator prompt %s missing content", prompt_id)
        return None
    return content


def _call_openai_pulse_evaluator(
    system_prompt: str,
    transcript_lines: List[str],
    session_doc: Dict[str, Any],
) -> Dict[str, Any]:
    """Call Azure OpenAI to run the PULSE 0–3 evaluator.

    Uses the same endpoint/api-version/api-key pattern as trainer_pulse_step and
    targets either OPENAI_DEPLOYMENT_PERSONA_HIGH_REASONING or
    OPENAI_DEPLOYMENT_PERSONA_CORE_CHAT.
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
        raise RuntimeError("Missing Azure OpenAI configuration for PULSE evaluator")

    url = f"{endpoint}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"

    user_payload = {
        "persona": session_doc.get("persona"),
        "sessionId": session_doc.get("session_id") or session_doc.get("sessionId"),
        "status": session_doc.get("status"),
        "transcript": transcript_lines,
    }

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
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
        raise RuntimeError("No choices returned from Azure OpenAI for evaluator")

    message = choices[0].get("message") or {}
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("Empty content from Azure OpenAI evaluator")

    return json.loads(content)


def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("feedback_session request: %s", req.method)

    if req.method == "OPTIONS":
        return _no_content()

    if req.method != "GET":
        return _error("Method not allowed", 405)

    if not _orchestrator_enabled():
        return _error(
            "Training orchestrator is disabled in this environment. "
            "Set TRAINING_ORCHESTRATOR_ENABLED to true to enable.",
            503,
        )

    session_id = None
    if hasattr(req, "route_params") and req.route_params:
        session_id = req.route_params.get("sessionId")
    if not session_id and req.params:
        session_id = req.params.get("sessionId")

    if not session_id:
        return _error("Missing sessionId", 400)

    session_doc = read_json(f"sessions/{session_id}/session.json")
    if not session_doc:
        return _error("Session not found", 404)

    transcript_lines = _load_transcript(session_id)
    scorecard = _load_scorecard(session_id)

    body: Dict[str, Any] = {
        "artifacts": {"transcript": transcript_lines},
        "session": {
            "sessionId": session_id,
            "persona": session_doc.get("persona"),
            "status": session_doc.get("status"),
        },
    }

    # Map optional scorecard fields into the flexible feedback contract expected by the UI.
    try:
        if isinstance(scorecard, dict) and scorecard:
            overall = scorecard.get("overall") or {}
            overall_score = overall.get("score")
            if isinstance(overall_score, (int, float)):
                body["overallScore"] = float(overall_score)

            rubric: List[Dict[str, Any]] = []
            components = [
                ("Behavioral Mastery (BCE)", scorecard.get("bce")),
                ("Methodology Fidelity (MCF)", scorecard.get("mcf")),
                ("Conversion Outcome (CPO)", scorecard.get("cpo")),
            ]
            for name, part in components:
                if not isinstance(part, dict):
                    continue
                score = part.get("score")
                if not isinstance(score, (int, float)):
                    continue
                notes = part.get("summary") or part.get("notes") or ""
                passed = part.get("passed") if isinstance(part.get("passed"), bool) else None
                rubric.append(
                    {
                        "name": name,
                        "score": score,
                        "passed": passed,
                        "notes": notes,
                    }
                )

            if rubric:
                body["rubric"] = rubric

            # Include raw scorecard for downstream consumers (e.g., admin or deeper UI views).
            body["scorecard"] = scorecard

            # Record a longitudinal analytics event capturing the overall scorecard.
            # This call is gated by PULSE_ANALYTICS_ENABLED inside analytics_events and
            # will no-op when analytics are disabled or misconfigured.
            record_session_scorecard_event(session_id, session_doc, scorecard)

            # Compute and store a readiness snapshot for the associated user when
            # readiness is enabled and a valid user_id is available on the session.
            compute_and_store_user_readiness_for_session(session_doc)
    except Exception as exc:  # noqa: BLE001
        logging.exception("feedback_session: failed to interpret scorecard for session %s: %s", session_id, exc)

    # Optionally run the PULSE 0–3 evaluator when enabled and transcript is available.
    try:
        evaluator_flag = os.getenv("PULSE_EVALUATOR_ENABLED", "false").strip().lower()
        evaluator_enabled = evaluator_flag in ("true", "1", "yes")
        if evaluator_enabled and transcript_lines:
            system_prompt = _load_evaluator_prompt()
            if system_prompt:
                eval_result = _call_openai_pulse_evaluator(system_prompt, transcript_lines, session_doc)
                if isinstance(eval_result, dict):
                    body["pulseEvaluator"] = eval_result
    except Exception as exc:  # noqa: BLE001
        logging.exception("feedback_session: PULSE evaluator failed for session %s: %s", session_id, exc)

    return _ok(body)
