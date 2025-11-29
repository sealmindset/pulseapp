import logging
import os
from typing import Any, Dict, List

import azure.functions as func
from psycopg.types.json import Json

from shared_code.blob import read_json, write_json, now_iso
from shared_code.http import json_ok, no_content, text_error
from shared_code.analytics_db import get_connection


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


def _extract_transcript_lines(body: Dict[str, Any]) -> List[str]:
    tx = body.get("transcript") if isinstance(body, dict) else None
    if isinstance(tx, list):
        return [str(x) for x in tx if str(x)]
    if isinstance(tx, str) and tx.strip():
        return [tx]
    return []


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

    # Optionally persist the final transcript when provided. This is best-effort
    # and does not affect the session completion response.
    lines = _extract_transcript_lines(body)
    if lines:
        transcript_doc: Dict[str, Any] = {"session_id": session_id, "transcript": lines}

        # Write blob transcript for compatibility with existing tooling.
        try:
            transcript_path = f"sessions/{session_id}/transcript.json"
            write_json(transcript_path, transcript_doc)
        except Exception as exc:  # noqa: BLE001
            logging.exception(
                "Failed to persist transcript blob for session %s: %s",
                session_id,
                exc,
            )

        # Insert into analytics.session_transcripts as the canonical
        # system-of-record for transcripts, when the analytics DB is
        # configured. Failures are logged but do not impact the HTTP
        # response.
        try:
            user_id = doc.get("user_id")
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO analytics.session_transcripts (
                            user_id,
                            session_id,
                            transcript_lines,
                            transcript_json
                        )
                        VALUES (
                            %(user_id)s,
                            %(session_id)s,
                            %(lines)s,
                            %(json)s
                        )
                        """,
                        {
                            "user_id": user_id,
                            "session_id": session_id,
                            "lines": lines,
                            "json": Json(transcript_doc),
                        },
                    )
        except Exception as exc:  # noqa: BLE001
            logging.exception(
                "session_complete: failed to persist transcript to analytics DB for session %s: %s",
                session_id,
                exc,
            )

    return _no_content()
