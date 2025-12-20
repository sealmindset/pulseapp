"""
Avatar token handler - provides authentication for client-side Speech SDK.

Returns token, region, ICE servers, and avatar configuration needed for
real-time WebRTC avatar streaming.
"""

import logging
import os

import azure.functions as func

from shared_code.avatar_service import get_avatar_token, get_avatar_config
from shared_code.http import json_ok, no_content, text_error


CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
}


def _orchestrator_enabled() -> bool:
    value = os.getenv("TRAINING_ORCHESTRATOR_ENABLED", "false").strip().lower()
    return value in ("true", "1", "yes")


def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("avatar_token request: %s", req.method)

    if req.method == "OPTIONS":
        return no_content(headers=CORS_HEADERS)

    if req.method != "POST":
        return text_error("Method not allowed", 405, headers=CORS_HEADERS)

    if not _orchestrator_enabled():
        return text_error(
            "Training orchestrator is disabled in this environment.",
            503,
            headers=CORS_HEADERS,
        )

    try:
        body = req.get_json()
    except Exception:
        body = {}

    persona_type = body.get("persona", "Relater") if isinstance(body, dict) else "Relater"

    # Get authentication token for Speech SDK
    token_info = get_avatar_token()
    if not token_info:
        import os
        key = os.getenv("AZURE_SPEECH_KEY", "")
        region = os.getenv("AZURE_SPEECH_REGION", "")
        logging.warning(
            "avatar_token: Avatar service unavailable. key_present=%s, region=%s",
            bool(key), region
        )
        return text_error(
            f"Avatar service unavailable. key_present={bool(key)}, region={region}",
            503,
            headers=CORS_HEADERS,
        )

    # Get persona-specific avatar configuration
    avatar_config = get_avatar_config(persona_type)

    response_data = {
        "token": token_info["token"],
        "region": token_info["region"],
        "iceServers": token_info.get("ice_servers"),
        "expiresIn": token_info.get("expires_in", 600),
        "avatarConfig": avatar_config,
    }

    logging.info("avatar_token: returning token for persona=%s, region=%s", 
                 persona_type, token_info["region"])

    return json_ok(response_data, headers=CORS_HEADERS)
