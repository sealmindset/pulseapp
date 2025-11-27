import json
import uuid
from datetime import datetime, timezone
from typing import Any, Mapping, Optional

import azure.functions as func


Headers = Optional[Mapping[str, str]]


def json_ok(body: Any, status: int = 200, headers: Headers = None) -> func.HttpResponse:
    return func.HttpResponse(
        body=json.dumps(body, ensure_ascii=False),
        status_code=status,
        mimetype="application/json",
        headers=headers,
    )


def no_content(headers: Headers = None) -> func.HttpResponse:
    return func.HttpResponse(status_code=204, headers=headers)


def text_error(message: str, status: int, headers: Headers = None) -> func.HttpResponse:
    return func.HttpResponse(body=message, status_code=status, headers=headers)


def json_error_envelope(code: str, message: str, status: int, headers: Headers = None) -> func.HttpResponse:
    """Return a structured JSON error envelope.

    Shape:
      {"error": {"code": code, "message": message}, "requestId": str, "timestamp": iso8601}

    This helper is for future use; existing endpoints may continue using text_error
    to avoid breaking clients until they are migrated to consume JSON errors.
    """

    envelope = {
        "error": {"code": code, "message": message},
        "requestId": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    combined_headers = dict(headers) if headers else {}
    combined_headers.setdefault("Content-Type", "application/json")

    return func.HttpResponse(
        body=json.dumps(envelope, ensure_ascii=False),
        status_code=status,
        mimetype="application/json",
        headers=combined_headers,
    )
