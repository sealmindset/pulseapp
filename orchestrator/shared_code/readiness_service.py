import logging
import os
import uuid
from typing import Any, Dict, List, Optional

from psycopg.types.json import Json

from . import analytics_db


_logger = logging.getLogger(__name__)

# Window configuration: last 30 days of events
_AGG_WINDOW_NAME = "30d"
_AGG_WINDOW_LABEL = "last_30_days"

# Readiness weights (can be refined later or moved to config)
_READINESS_WEIGHTS = {
    "readiness_technical": 0.3,
    "readiness_communication": 0.3,
    "readiness_structure": 0.2,
    "readiness_behavioral": 0.2,
}

# Mapping from skill_tag -> readiness component
_COMPONENT_SKILL_TAGS = {
    "technical_depth": "readiness_technical",
    "communication": "readiness_communication",
    "structure": "readiness_structure",
    "behavioral_examples": "readiness_behavioral",
}


def _readiness_enabled() -> bool:
    value = os.getenv("PULSE_READINESS_ENABLED", "false").strip().lower()
    return value in ("true", "1", "yes")


def _extract_user_id(session_doc: Dict[str, Any]) -> Optional[str]:
    raw = session_doc.get("user_id")
    if not isinstance(raw, str) or not raw.strip():
        _logger.info("readiness_service: no user_id on session; skipping readiness computation")
        return None
    try:
        uuid.UUID(raw)
    except ValueError:
        _logger.warning("readiness_service: user_id is not a valid UUID; skipping readiness computation")
        return None
    return raw


def _compute_skill_aggregates(cur, user_id: str) -> List[Dict[str, Any]]:
    """Compute per-skill aggregates from analytics.session_events.

    Returns a list of dicts: {"skill_tag", "avg_score", "sample_size"}.
    """

    cur.execute(
        """
        SELECT
            skill_tag,
            AVG(score) AS avg_score,
            COUNT(*)   AS sample_size
        FROM analytics.session_events
        WHERE user_id = %(user_id)s
          AND occurred_at >= now() - INTERVAL '30 days'
        GROUP BY skill_tag
        """,
        {"user_id": user_id},
    )
    rows = cur.fetchall() or []

    aggregates: List[Dict[str, Any]] = []
    for skill_tag, avg_score, sample_size in rows:
        aggregates.append(
            {
                "skill_tag": skill_tag,
                "avg_score": float(avg_score),
                "sample_size": int(sample_size),
            }
        )
    return aggregates


def _upsert_user_skill_agg(cur, user_id: str, aggregates: List[Dict[str, Any]]) -> None:
    for agg in aggregates:
        payload = {
            "user_id": user_id,
            "skill_tag": agg["skill_tag"],
            "window": _AGG_WINDOW_NAME,
            "avg_score": agg["avg_score"],
            "sample_size": agg["sample_size"],
        }
        cur.execute(
            """
            INSERT INTO analytics.user_skill_agg (
                user_id,
                skill_tag,
                window,
                avg_score,
                sample_size,
                last_updated
            )
            VALUES (
                %(user_id)s,
                %(skill_tag)s,
                %(window)s,
                %(avg_score)s,
                %(sample_size)s,
                now()
            )
            ON CONFLICT (user_id, skill_tag, window)
            DO UPDATE SET
                avg_score = EXCLUDED.avg_score,
                sample_size = EXCLUDED.sample_size,
                last_updated = now()
            """,
            payload,
        )


def _compute_components_from_aggregates(aggregates: List[Dict[str, Any]]) -> Dict[str, Optional[float]]:
    # Initialize accumulators
    sums: Dict[str, float] = {
        "readiness_technical": 0.0,
        "readiness_communication": 0.0,
        "readiness_structure": 0.0,
        "readiness_behavioral": 0.0,
    }
    weights: Dict[str, int] = {k: 0 for k in sums.keys()}

    overall_from_events: Optional[float] = None

    for agg in aggregates:
        tag = agg["skill_tag"]
        avg_score = agg["avg_score"]
        sample_size = agg["sample_size"]

        if tag == "overall":
            overall_from_events = avg_score

        component = _COMPONENT_SKILL_TAGS.get(tag)
        if not component:
            continue

        sums[component] += avg_score * sample_size
        weights[component] += sample_size

    components: Dict[str, Optional[float]] = {}
    for key in sums.keys():
        if weights[key] > 0:
            components[key] = round(sums[key] / weights[key], 2)
        else:
            components[key] = None

    components["overall_from_events"] = overall_from_events
    return components


def _compute_overall_from_components(components: Dict[str, Optional[float]]) -> Optional[float]:
    # If we have any component values, compute weighted overall using the
    # configured weights, renormalizing to the subset of present components.
    present_keys = [k for k in _READINESS_WEIGHTS.keys() if components.get(k) is not None]
    if present_keys:
        total_w = sum(_READINESS_WEIGHTS[k] for k in present_keys)
        if total_w <= 0:
            return None
        overall = 0.0
        for k in present_keys:
            w = _READINESS_WEIGHTS[k] / total_w
            overall += components[k] * w  # type: ignore[operator]
        return round(overall, 2)

    # Fallback: if we only have an "overall" skill_tag aggregate, use that.
    overall_from_events = components.get("overall_from_events")
    if isinstance(overall_from_events, (int, float)):
        return round(float(overall_from_events), 2)

    return None


def compute_and_store_user_readiness(user_id: str) -> Optional[Dict[str, Any]]:
    """Compute aggregates and store a readiness snapshot for the given user.

    Returns a dict with the stored snapshot fields, or None when no data was
    available or readiness is disabled.
    """

    if not _readiness_enabled():
        _logger.info("readiness_service: disabled via PULSE_READINESS_ENABLED; skipping")
        return None

    try:
        with analytics_db.get_connection() as conn:
            with conn.cursor() as cur:
                aggregates = _compute_skill_aggregates(cur, user_id)
                if not aggregates:
                    _logger.info("readiness_service: no session_events for user %s; skipping", user_id)
                    return None

                _upsert_user_skill_agg(cur, user_id, aggregates)

                components = _compute_components_from_aggregates(aggregates)
                overall = _compute_overall_from_components(components)
                if overall is None:
                    _logger.info("readiness_service: unable to compute readiness_overall for user %s; skipping", user_id)
                    return None

                snapshot = {
                    "user_id": user_id,
                    "readiness_overall": overall,
                    "readiness_technical": components.get("readiness_technical"),
                    "readiness_communication": components.get("readiness_communication"),
                    "readiness_structure": components.get("readiness_structure"),
                    "readiness_behavioral": components.get("readiness_behavioral"),
                    "window": _AGG_WINDOW_NAME,
                    "window_label": _AGG_WINDOW_LABEL,
                }

                meta = {
                    "formula_version": "v1",
                    "window_name": _AGG_WINDOW_NAME,
                    "window_label": _AGG_WINDOW_LABEL,
                    "weights": _READINESS_WEIGHTS,
                    "source": "session_events",
                }

                cur.execute(
                    """
                    INSERT INTO analytics.user_readiness (
                        user_id,
                        snapshot_at,
                        readiness_overall,
                        readiness_technical,
                        readiness_communication,
                        readiness_structure,
                        readiness_behavioral,
                        meta
                    )
                    VALUES (
                        %(user_id)s,
                        now(),
                        %(readiness_overall)s,
                        %(readiness_technical)s,
                        %(readiness_communication)s,
                        %(readiness_structure)s,
                        %(readiness_behavioral)s,
                        %(meta)s
                    )
                    """,
                    {
                        "user_id": snapshot["user_id"],
                        "readiness_overall": snapshot["readiness_overall"],
                        "readiness_technical": snapshot["readiness_technical"],
                        "readiness_communication": snapshot["readiness_communication"],
                        "readiness_structure": snapshot["readiness_structure"],
                        "readiness_behavioral": snapshot["readiness_behavioral"],
                        "meta": Json(meta),
                    },
                )
    except Exception as exc:  # noqa: BLE001
        _logger.exception("readiness_service: failed to compute/store readiness for user %s: %s", user_id, exc)
        return None

    _logger.info(
        "readiness_service: stored readiness snapshot for user %s (overall=%s)",
        user_id,
        snapshot["readiness_overall"],
    )
    return snapshot


def compute_and_store_user_readiness_for_session(session_doc: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Entry point used by orchestrator endpoints that have a session_doc.

    This extracts a user_id, validates it as a UUID, and delegates to
    compute_and_store_user_readiness. When user_id is missing or invalid the
    function is a no-op.
    """

    user_id = _extract_user_id(session_doc)
    if not user_id:
        return None
    return compute_and_store_user_readiness(user_id)
