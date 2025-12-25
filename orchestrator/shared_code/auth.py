"""
Simple shared secret validation for Function App.
Defense-in-depth - the UI already authenticates users.
"""

import os
import hmac
import logging
from functools import wraps
from typing import Callable, Any

import azure.functions as func


def validate_shared_secret(req: func.HttpRequest) -> bool:
    """
    Validate X-Function-Key header matches our secret.
    Returns True if valid OR if no secret is configured (dev mode).
    """
    expected = os.environ.get('FUNCTION_APP_SHARED_SECRET', '')

    # No secret configured = skip validation (development)
    if not expected:
        return True

    provided = req.headers.get('X-Function-Key', '')

    if not provided:
        logging.warning("auth: Missing X-Function-Key header")
        return False

    # Constant-time comparison to prevent timing attacks
    is_valid = hmac.compare_digest(expected, provided)

    if not is_valid:
        logging.warning("auth: Invalid X-Function-Key provided")

    return is_valid


def require_auth(func_handler: Callable) -> Callable:
    """
    Decorator to require shared secret for a function.

    Usage:
        @require_auth
        def main(req: func.HttpRequest) -> func.HttpResponse:
            ...
    """
    @wraps(func_handler)
    def wrapper(req: func.HttpRequest, *args: Any, **kwargs: Any) -> func.HttpResponse:
        # Skip for OPTIONS (CORS preflight)
        if req.method == "OPTIONS":
            return func_handler(req, *args, **kwargs)

        if not validate_shared_secret(req):
            return func.HttpResponse(
                body='{"error": "Unauthorized"}',
                status_code=401,
                mimetype="application/json",
            )

        return func_handler(req, *args, **kwargs)

    return wrapper
