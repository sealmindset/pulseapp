import json
import logging
import os
from typing import Any, Dict

import azure.functions as func

from shared_code.blob import read_json, write_json, now_iso
from shared_code.http import json_ok, no_content, text_error

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, PUT, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
}


def _ok(body: Any, status: int = 200) -> func.HttpResponse:
    return json_ok(body, status=status, headers=CORS_HEADERS)


def _no_content() -> func.HttpResponse:
    return no_content(headers=CORS_HEADERS)


def _error(msg: str, status: int) -> func.HttpResponse:
    return text_error(msg, status=status, headers=CORS_HEADERS)


def _writes_enabled() -> bool:
    v = os.getenv("ADMIN_EDIT_ENABLED", "false").strip().lower()
    return v in ("true", "1", "yes")


def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("admin_agents request: %s", req.method)

    if req.method == "OPTIONS":
        return _no_content()

    if req.method == "GET":
        data = read_json("agents.json") or {}
        agents = data.get("agents") if isinstance(data, dict) else None
        if not isinstance(agents, list):
            agents = []
        logging.info("admin_agents list: count=%d", len(agents))
        return _ok({"agents": agents})

    if req.method == "PUT":
        if not _writes_enabled():
            return _error("Writes disabled in this environment", 403)
        try:
            body: Dict[str, Any] = req.get_json()
        except Exception:
            return _error("Invalid JSON", 400)
        agents = body.get("agents")
        if not isinstance(agents, list):
            return _error("'agents' must be a list", 400)
        # stamp basic metadata
        now = now_iso()
        for a in agents:
            if isinstance(a, dict):
                a.setdefault("updatedAt", now)
                a.setdefault("updatedBy", "dev-operator")
        logging.info("admin_agents update: count=%d", len(agents))
        write_json("agents.json", {"agents": agents})
        return _ok({"ok": True})

    return _error("Method not allowed", 405)
