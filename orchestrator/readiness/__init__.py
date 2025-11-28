import logging
import os
from typing import Any, Dict, List

import azure.functions as func

from shared_code.http import json_ok, no_content, text_error
from shared_code.analytics_db import get_connection


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


def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("readiness request: %s", req.method)

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

    user_id = None
    if hasattr(req, "route_params") and req.route_params:
        user_id = req.route_params.get("userId")
    if not user_id and req.params:
        user_id = req.params.get("userId")

    if not user_id:
        return _error("Missing userId", 400)

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        snapshot_at,
                        readiness_overall,
                        readiness_technical,
                        readiness_communication,
                        readiness_structure,
                        readiness_behavioral
                    FROM analytics.user_readiness
                    WHERE user_id = %s
                    ORDER BY snapshot_at DESC
                    LIMIT 20
                    """,
                    (user_id,),
                )
                rows = cur.fetchall() or []
    except Exception as exc:  # noqa: BLE001
        logging.exception("readiness: failed to load readiness history for user %s: %s", user_id, exc)
        return _error("Failed to load readiness", 500)

    history: List[Dict[str, Any]] = []
    for snapshot_at, overall, technical, communication, structure, behavioral in rows:
        history.append(
            {
                "timestamp": snapshot_at.isoformat() if snapshot_at is not None else None,
                "overall": float(overall) if overall is not None else None,
                "technical": float(technical) if technical is not None else None,
                "communication": float(communication) if communication is not None else None,
                "structure": float(structure) if structure is not None else None,
                "behavioral": float(behavioral) if behavioral is not None else None,
            }
        )

    latest = history[0] if history else None

    body: Dict[str, Any] = {
        "userId": user_id,
        "latest": latest,
        "history": history,
    }

    return _ok(body)
