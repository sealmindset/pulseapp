import logging
from datetime import datetime, timezone
from typing import Any, Dict

from psycopg.types.json import Json

from . import analytics_db


_logger = logging.getLogger(__name__)


def _analytics_enabled() -> bool:
    # Simple feature flag so analytics can be safely disabled in some envs.
    from os import getenv

    value = getenv("PULSE_ANALYTICS_ENABLED", "false").strip().lower()
    return value in ("true", "1", "yes")


def record_session_scorecard_event(session_id: str, session_doc: Dict[str, Any], scorecard: Dict[str, Any]) -> None:
    """Record a high-level session scorecard event into analytics.session_events.

    This is a minimal integration point that stores the overall session score
    and raw scorecard JSON so that longitudinal analytics can evolve without
    changing the orchestrator contract.
    """

    if not _analytics_enabled():
        return

    if not isinstance(scorecard, dict) or not scorecard:
        return

    overall = scorecard.get("overall") or {}
    score = overall.get("score")
    if not isinstance(score, (int, float)):
        return

    user_id = session_doc.get("user_id")
    persona = session_doc.get("persona")

    payload = {
        "user_id": user_id,
        "session_id": session_id,
        "occurred_at": datetime.now(timezone.utc),
        "scenario_id": persona,
        "pulse_step": "session_end",
        "skill_tag": "overall",
        "score": float(score),
        "raw_metrics": Json(scorecard),
        "notes": None,
    }

    try:
        with analytics_db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO analytics.session_events (
                        user_id,
                        session_id,
                        occurred_at,
                        scenario_id,
                        pulse_step,
                        skill_tag,
                        score,
                        raw_metrics,
                        notes
                    )
                    VALUES (
                        %(user_id)s,
                        %(session_id)s,
                        %(occurred_at)s,
                        %(scenario_id)s,
                        %(pulse_step)s,
                        %(skill_tag)s,
                        %(score)s,
                        %(raw_metrics)s,
                        %(notes)s
                    )
                    """,
                    payload,
                )
    except Exception as exc:  # noqa: BLE001
        _logger.exception("analytics_events: failed to record scorecard event for session %s: %s", session_id, exc)
