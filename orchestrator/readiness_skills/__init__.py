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
    logging.info("readiness_skills request: %s", req.method)

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

    window = "30d"

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        skill_tag,
                        window,
                        avg_score,
                        sample_size
                    FROM analytics.user_skill_agg
                    WHERE user_id = %s
                      AND window = %s
                    ORDER BY skill_tag
                    """,
                    (user_id, window),
                )
                rows = cur.fetchall() or []
    except Exception as exc:  # noqa: BLE001
        logging.exception("readiness_skills: failed to load skill aggregates for user %s: %s", user_id, exc)
        return _error("Failed to load skill trends", 500)

    skills: List[Dict[str, Any]] = []
    for skill_tag, row_window, avg_score, sample_size in rows:
        skills.append(
            {
                "skillTag": skill_tag,
                "window": row_window,
                "avgScore": float(avg_score) if avg_score is not None else None,
                "sampleSize": int(sample_size) if sample_size is not None else 0,
            }
        )

    body: Dict[str, Any] = {
        "userId": user_id,
        "window": window,
        "skills": skills,
    }

    return _ok(body)
