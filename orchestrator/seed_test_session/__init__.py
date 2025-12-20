"""
Seed test session data for development testing.

Creates a test session with scorecard and transcript data so the feedback page
can be tested without completing a full conversation flow.
"""

import json
import logging
import os
from typing import Any, Dict

import azure.functions as func

from shared_code.blob import write_json, read_json
from shared_code.http import json_ok, no_content, text_error


CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
}

# Default test session ID
DEFAULT_TEST_SESSION_ID = "dev-test-session-001"


def _create_test_session(session_id: str) -> Dict[str, Any]:
    """Create a test session document."""
    return {
        "session_id": session_id,
        "persona": "Relater",
        "status": "completed",
        "created_at": "2025-01-01T00:00:00Z",
        "completed_at": "2025-01-01T00:30:00Z",
    }


def _create_test_scorecard(outcome: str = "won") -> Dict[str, Any]:
    """Create a test scorecard with sample data."""
    if outcome == "won":
        return {
            "overall": {
                "score": 85,
                "raw_score": 2.55,
                "passed": True,
            },
            "bce": {
                "score": 3.0,
                "passed": True,
                "summary": "Reached PULSE stage 5 (Earn). Excellent! Completed all PULSE stages.",
            },
            "mcf": {
                "score": 2.5,
                "passed": True,
                "summary": "Trust score: 8/10. No missteps detected.",
            },
            "cpo": {
                "score": 3.0,
                "passed": True,
                "summary": "Successfully closed the sale!",
            },
            "pulse_details": {
                "final_stage": 5,
                "stage_name": "Earn",
                "trust_score": 8,
                "sale_outcome": "won",
                "missteps": [],
                "total_exchanges": 12,
            },
        }
    else:
        return {
            "overall": {
                "score": 33,
                "raw_score": 1.0,
                "passed": False,
            },
            "bce": {
                "score": 1.5,
                "passed": False,
                "summary": "Reached PULSE stage 3 (Link). Good progress, but didn't complete the full PULSE cycle.",
            },
            "mcf": {
                "score": 1.0,
                "passed": False,
                "summary": "Trust score: 3/10. Missteps: premature close, ignored objection.",
            },
            "cpo": {
                "score": 0,
                "passed": False,
                "summary": "Customer walked away. Review approach and try again.",
            },
            "pulse_details": {
                "final_stage": 3,
                "stage_name": "Link",
                "trust_score": 3,
                "sale_outcome": "lost",
                "missteps": ["premature close", "ignored objection"],
                "total_exchanges": 6,
            },
        }


def _create_test_transcript() -> Dict[str, Any]:
    """Create a test transcript."""
    return {
        "transcript": [
            "Trainee: Hi there! How can I help you today?",
            "Customer: I'm looking for a solution to help my team collaborate better.",
            "Trainee: That's great! Can you tell me more about the challenges your team is facing?",
            "Customer: We have people in different time zones and it's hard to stay in sync.",
            "Trainee: I understand. Many of our customers face similar challenges. How many people are on your team?",
            "Customer: About 25 people across 4 different countries.",
            "Trainee: Perfect. Our platform is designed exactly for distributed teams like yours.",
            "Customer: That sounds interesting. What makes it different from other tools?",
            "Trainee: Great question! We focus on async-first communication with smart notifications.",
            "Customer: I like that approach. What would it cost for our team size?",
            "Trainee: For 25 users, you'd be looking at our Team plan at $15 per user per month.",
            "Customer: That seems reasonable. Can we start with a trial?",
        ],
    }


def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("seed_test_session request: %s", req.method)

    if req.method == "OPTIONS":
        return no_content(headers=CORS_HEADERS)

    if req.method != "POST":
        return text_error("Method not allowed", 405, headers=CORS_HEADERS)

    # Check if seeding is enabled (only in dev/test environments)
    seed_enabled = os.getenv("ALLOW_TEST_SEED", "false").strip().lower()
    if seed_enabled not in ("true", "1", "yes"):
        return text_error(
            "Test seeding is disabled. Set ALLOW_TEST_SEED=true to enable.",
            403,
            headers=CORS_HEADERS,
        )

    try:
        body = req.get_json()
    except Exception:
        body = {}

    session_id = body.get("sessionId", DEFAULT_TEST_SESSION_ID) if isinstance(body, dict) else DEFAULT_TEST_SESSION_ID
    outcome = body.get("outcome", "won") if isinstance(body, dict) else "won"

    # Create test data
    session_doc = _create_test_session(session_id)
    scorecard = _create_test_scorecard(outcome)
    transcript = _create_test_transcript()

    # Save to blob storage
    try:
        write_json(f"sessions/{session_id}/session.json", session_doc)
        write_json(f"sessions/{session_id}/scorecard.json", scorecard)
        write_json(f"sessions/{session_id}/transcript.json", transcript)
        
        logging.info("seed_test_session: Created test session %s with outcome %s", session_id, outcome)
        
        return json_ok({
            "success": True,
            "sessionId": session_id,
            "outcome": outcome,
            "message": f"Test session '{session_id}' created with {outcome} outcome",
        }, headers=CORS_HEADERS)
        
    except Exception as e:
        logging.exception("seed_test_session: Failed to create test session: %s", e)
        return text_error(f"Failed to create test session: {str(e)}", 500, headers=CORS_HEADERS)
