"""
Session start handler for PULSE training sessions.

Creates a new training session and optionally generates an intro avatar video.
"""

import logging
import os
import uuid
from typing import Any, Dict, Optional

import azure.functions as func

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


def _error(message: str, status: int) -> func.HttpResponse:
    return text_error(message, status=status, headers=CORS_HEADERS)


def _orchestrator_enabled() -> bool:
    value = os.getenv("TRAINING_ORCHESTRATOR_ENABLED", "false").strip().lower()
    return value in ("true", "1", "yes")


def _extract_user_id(req: func.HttpRequest, body: Dict[str, Any]) -> Optional[str]:
    """Extract an optional user_id UUID from the request.

    This is intentionally soft-fail: if userId is missing or invalid, we
    simply return None and the session proceeds without a user_id attached.
    Readiness and analytics layers will only operate when a valid UUID is
    present.
    """

    raw: Any = None
    if isinstance(body, dict):
        raw = body.get("userId") or body.get("user_id")
    if not raw:
        raw = req.headers.get("X-PULSE-User-Id")

    if not isinstance(raw, str) or not raw.strip():
        return None

    candidate = raw.strip()
    try:
        uuid.UUID(candidate)
    except ValueError:
        logging.warning("session_start: ignoring invalid userId '%s'", candidate)
        return None

    return candidate


def _generate_intro_avatar(persona: str, session_id: str) -> Dict[str, Any]:
    """Generate an introductory avatar video for the session."""
    try:
        from shared_code.avatar_service import generate_intro_avatar, is_avatar_service_available
        
        if not is_avatar_service_available():
            logging.info("session_start: avatar service not available")
            return {"avatarUrl": None, "avatarVideoUrl": None}
        
        result = generate_intro_avatar(persona_type=persona, session_id=session_id)
        
        return {
            "avatarUrl": None,  # Static image fallback
            "avatarVideoUrl": result.get("video_url"),
            "avatarVideoBase64": result.get("video_base64"),
            "avatarEmotion": result.get("emotion", "neutral"),
        }
    except ImportError:
        logging.warning("session_start: avatar_service not available")
        return {"avatarUrl": None, "avatarVideoUrl": None}
    except Exception as exc:
        logging.exception("session_start: avatar generation failed: %s", exc)
        return {"avatarUrl": None, "avatarVideoUrl": None}


def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("session_start request: %s", req.method)

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

    persona = body.get("persona") if isinstance(body, dict) else None
    if not persona:
        persona = "Relater"  # Default persona
    
    user_id = _extract_user_id(req, body)

    session_id = str(uuid.uuid4())
    doc: Dict[str, Any] = {
        "session_id": session_id,
        "created_at": now_iso(),
        "persona": persona,
        "request": body,
        "status": "active",
    }

    if user_id is not None:
        doc["user_id"] = user_id

    try:
        write_json(f"sessions/{session_id}/session.json", doc)
    except Exception as exc:  # noqa: BLE001
        logging.exception("Failed to persist session start: %s", exc)
        return _error("Failed to start session", 500)

    # Generate intro avatar video (async-friendly, non-blocking on failure)
    avatar_data = _generate_intro_avatar(persona, session_id)

    response_data: Dict[str, Any] = {
        "sessionId": session_id,
        "persona": {
            "type": persona,
            "displayName": _get_persona_display_name(persona),
        },
        **avatar_data,
    }

    return _ok(response_data)


def _get_persona_display_name(persona: str) -> str:
    """Get a display-friendly name for the persona."""
    names = {
        "Director": "The Director",
        "Relater": "The Relater", 
        "Socializer": "The Socializer",
        "Thinker": "The Thinker",
    }
    return names.get(persona, persona)
