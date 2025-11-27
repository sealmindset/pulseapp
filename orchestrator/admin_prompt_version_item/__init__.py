import json
import logging
from typing import Any

import azure.functions as func

from shared_code.blob import read_json
from shared_code.http import json_ok, no_content, text_error

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
}


def _ok(body: Any, status: int = 200) -> func.HttpResponse:
    return json_ok(body, status=status, headers=CORS_HEADERS)


def _no_content() -> func.HttpResponse:
    return no_content(headers=CORS_HEADERS)


def _error(msg: str, status: int) -> func.HttpResponse:
    return text_error(msg, status=status, headers=CORS_HEADERS)


def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info(
        "admin_prompt_version_item request: %s id=%s version=%s",
        req.method,
        req.route_params.get("id"),
        req.route_params.get("version"),
    )

    if req.method == "OPTIONS":
        return _no_content()

    if req.method != "GET":
        return _error("Method not allowed", 405)

    pid = (req.route_params.get("id") or "").strip()
    ver = (req.route_params.get("version") or "").strip()
    if not pid or not ver:
        return _error("Missing id or version", 400)

    path = f"prompts/{pid}/versions/{ver}.json"
    doc = read_json(path)
    if doc is None:
        return _error("Not found", 404)
    logging.info("admin_prompt_version_item get: id=%s version=%s", pid, ver)
    return _ok(doc)
