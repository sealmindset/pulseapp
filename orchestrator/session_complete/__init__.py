import logging
import os
from typing import Any, Dict

import azure.functions as func

from shared_code.blob import read_json, write_json, now_iso
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


def _error(message: str, status: int) -> func.HttpResponse:
    return text_error(message, status=status, headers=CORS_HEADERS)


def _orchestrator_enabled() -> bool:
    value = os.getenv("TRAINING_ORCHESTRATOR_ENABLED", "false").strip().lower()
    return value in ("true", "1", "yes")


def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("session_complete request: %s", req.method)

    if req.method == "OPTIONS":
        return _no_content()

    if req.method != "POST":
        return _error("Method not allowed", 405)

    if not _orchestrator_enabled():
        return _error(
            "Training orchestrator is disabled in this environment. "
            "Set TRAINING_ORCHESTRATOR_ENABLED to true to enable.",
            503,
        )

    try:
        body: Dict[str, Any] = req.get_json()
    except Exception:  # noqa: BLE001
        return _error("Invalid JSON", 400)

    session_id = str(body.get("sessionId") or "") if isinstance(body, dict) else ""
    if not session_id:
        return _error("Missing sessionId", 400)

    path = f"sessions/{session_id}/session.json"
    doc = read_json(path) or {"session_id": session_id}
    doc["status"] = "completed"
    doc["completed_at"] = now_iso()

    try:
        write_json(path, doc)
    except Exception as exc:  # noqa: BLE001
        logging.exception("Failed to persist session completion: %s", exc)
        return _error("Failed to complete session", 500)

    return _no_content()
