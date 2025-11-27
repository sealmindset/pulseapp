import json
import logging
import os
from typing import Any, Dict

import azure.functions as func

from shared_code.blob import (
    read_json,
    write_json,
    list_blob_names,
    blob_exists,
    now_iso,
    new_prompt_id_from_title,
)
from shared_code.http import json_ok, no_content, text_error

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
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


# Utilities for prompts
CURRENT_PREFIX = "prompts/"


def _current_blob(id_: str) -> str:
    return f"{CURRENT_PREFIX}{id_}.json"


def _version_blob(id_: str, version: int) -> str:
    return f"{CURRENT_PREFIX}{id_}/versions/{version}.json"


def _list_current_prompt_ids():
    names = list_blob_names(CURRENT_PREFIX)
    out = []
    for n in names:
        if "/versions/" in n:
            continue
        if n.startswith(CURRENT_PREFIX) and n.endswith(".json"):
            pid = n[len(CURRENT_PREFIX) : -len(".json")]
            out.append(pid)
    return out


def _summarize_prompt(id_: str):
    data = read_json(_current_blob(id_)) or {}
    if not isinstance(data, dict):
        return None
    return {
        "id": id_,
        "title": data.get("title"),
        "type": data.get("type"),
        "agentId": data.get("agentId"),
        "version": data.get("version"),
        "updatedAt": data.get("updatedAt"),
    }


def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("admin_prompts request: %s", req.method)

    if req.method == "OPTIONS":
        return _no_content()

    if req.method == "GET":
        ids = _list_current_prompt_ids()
        items = []
        for id_ in ids:
            s = _summarize_prompt(id_)
            if s:
                items.append(s)
        logging.info("admin_prompts list: count=%d", len(items))
        return _ok({"items": items})

    if req.method == "POST":
        if not _writes_enabled():
            return _error("Writes disabled in this environment", 403)
        try:
            body: Dict[str, Any] = req.get_json()
        except Exception:
            return _error("Invalid JSON", 400)
        title = (body.get("title") or "").strip()
        content = (body.get("content") or "").strip()
        ptype = (body.get("type") or "system").strip()
        agent_id = (body.get("agentId") or "").strip()
        pid = (body.get("id") or "").strip()
        if not title or not content:
            return _error("'title' and 'content' are required", 400)
        if not pid:
            pid = new_prompt_id_from_title(title)
        if blob_exists(_current_blob(pid)):
            return _error("Prompt id already exists", 409)
        now = now_iso()
        obj = {
            "id": pid,
            "title": title,
            "type": ptype or "system",
            "agentId": agent_id or None,
            "content": content,
            "version": 1,
            "updatedAt": now,
            "updatedBy": "dev-operator",
        }
        logging.info(
            "admin_prompts create: id=%s type=%s agentId=%s",
            pid,
            ptype or "system",
            agent_id or None,
        )
        write_json(_current_blob(pid), obj)
        write_json(_version_blob(pid, 1), obj)
        return _ok(obj, 201)

    return _error("Method not allowed", 405)
