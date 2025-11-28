import logging
import os

import azure.functions as func

from shared_code.http import no_content, text_error


CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
}


def _no_content() -> func.HttpResponse:
    return no_content(headers=CORS_HEADERS)


def _error(message: str, status: int) -> func.HttpResponse:
    return text_error(message, status=status, headers=CORS_HEADERS)


def _orchestrator_enabled() -> bool:
    value = os.getenv("TRAINING_ORCHESTRATOR_ENABLED", "false").strip().lower()
    return value in ("true", "1", "yes")


def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("audio_chunk request: %s", req.method)

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

    session_id = req.params.get("sessionId") if req.params else None
    if not session_id:
        return _error("Missing sessionId", 400)

    # Phase A: accept audio and acknowledge receipt without performing STT/TTS.
    return func.HttpResponse(
        body=(
            "Audio chunk received for session %s; audio processing is not yet "
            "configured in this environment." % session_id
        ),
        status_code=200,
        headers=CORS_HEADERS,
        mimetype="text/plain",
    )
