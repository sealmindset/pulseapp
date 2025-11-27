import json
import logging
from typing import Any, List

import azure.functions as func

from shared_code.blob import list_blob_names, read_json
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
    logging.info("admin_prompt_versions request: %s %s", req.method, req.route_params.get("id"))

    if req.method == "OPTIONS":
        return _no_content()

    if req.method != "GET":
        return _error("Method not allowed", 405)

    pid = (req.route_params.get("id") or "").strip()
    if not pid:
        return _error("Missing id", 400)

    prefix = f"prompts/{pid}/versions/"
    names: List[str] = list_blob_names(prefix)
    versions = []
    for n in names:
        if not n.endswith(".json"):
            continue
        # n like prompts/<id>/versions/<ver>.json
        try:
            ver_str = n.rsplit("/", 1)[-1][:-5]
            ver = int(ver_str)
        except Exception:
            continue
        doc = read_json(n) or {}
        versions.append({
            "version": ver,
            "updatedAt": doc.get("updatedAt"),
            "updatedBy": doc.get("updatedBy"),
        })
    versions.sort(key=lambda x: int(x.get("version") or 0), reverse=True)
    logging.info("admin_prompt_versions list: id=%s count=%d", pid, len(versions))
    return _ok({"items": versions})
