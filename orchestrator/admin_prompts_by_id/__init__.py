import json
import logging
import os
from typing import Any, Dict

import azure.functions as func

from shared_code.blob import read_json, write_json, blob_exists, now_iso
from shared_code.http import json_ok, no_content, text_error

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, PUT, DELETE, OPTIONS",
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


def _current_blob(id_: str) -> str:
    return f"prompts/{id_}.json"


def _version_blob(id_: str, version: int) -> str:
    return f"prompts/{id_}/versions/{version}.json"


def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("admin_prompts_by_id request: %s %s", req.method, req.route_params.get("id"))

    if req.method == "OPTIONS":
        return _no_content()

    id_ = (req.route_params.get("id") or "").strip()
    if not id_:
        return _error("Missing id", 400)

    cur_path = _current_blob(id_)

    if req.method == "GET":
        data = read_json(cur_path)
        if data is None:
            return _error("Not found", 404)
        logging.info("admin_prompts_by_id get: id=%s", id_)
        return _ok(data)

    if req.method == "PUT":
        if not _writes_enabled():
            return _error("Writes disabled in this environment", 403)
        current = read_json(cur_path)
        if current is None:
            return _error("Not found", 404)
        try:
            body: Dict[str, Any] = req.get_json()
        except Exception:
            return _error("Invalid JSON", 400)
        # soft concurrency check: log version mismatch but do not reject (Phase 3)
        try:
            current_ver = int(current.get("version") or 0)
        except Exception:
            current_ver = 0
        client_ver_raw = body.get("version") if isinstance(body, dict) else None
        if client_ver_raw is not None:
            try:
                client_ver = int(client_ver_raw)
            except Exception:
                logging.warning(
                    "admin_prompts_by_id update: id=%s invalid client version %r (current=%s)",
                    id_,
                    client_ver_raw,
                    current_ver,
                )
            else:
                if client_ver != current_ver:
                    logging.warning(
                        "admin_prompts_by_id update: id=%s version mismatch client=%s current=%s",
                        id_,
                        client_ver,
                        current_ver,
                    )
        # merge fields
        updated = dict(current)
        for k in ("title", "type", "agentId", "content"):
            if k in body and body[k] is not None:
                updated[k] = body[k]
        # version bump
        ver = int(updated.get("version") or 0) + 1
        updated["version"] = ver
        updated["updatedAt"] = now_iso()
        updated["updatedBy"] = "dev-operator"
        logging.info(
            "admin_prompts_by_id update: id=%s new_version=%s", id_, ver
        )
        write_json(cur_path, updated)
        write_json(_version_blob(id_, ver), updated)
        return _ok(updated)

    if req.method == "DELETE":
        if not _writes_enabled():
            return _error("Writes disabled in this environment", 403)
        current = read_json(cur_path)
        if current is None:
            return _error("Not found", 404)
        ver = int(current.get("version") or 0) + 1
        current["version"] = ver
        current["deleted"] = True
        current["updatedAt"] = now_iso()
        current["updatedBy"] = "dev-operator"
        logging.info(
            "admin_prompts_by_id delete: id=%s tombstone_version=%s", id_, ver
        )
        write_json(cur_path, current)
        write_json(_version_blob(id_, ver), current)
        return _ok({"ok": True})

    return _error("Method not allowed", 405)
