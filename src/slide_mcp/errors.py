"""Maps Slide API failures to the fixed MCP error envelope (SOP §4.2).

The vendor's raw `message` / `details` are never forwarded verbatim — only the HTTP
status code and the `codes` list, which Slide documents as a closed vocabulary that
never echoes request input back to the caller.
"""

from __future__ import annotations

import json

from .api_client import SlideAPIError
from .error_codes import map_status_to_code

RETRYABLE_CODES = {"rate_limited", "upstream_error"}


def envelope(code: str, message: str) -> str:
    return json.dumps(
        {"error": {"code": code, "message": message, "retryable": code in RETRYABLE_CODES}},
        ensure_ascii=False,
        separators=(",", ":"),
    )


def not_configured(message: str) -> str:
    return envelope("not_configured", message)


def from_slide_error(exc: SlideAPIError) -> str:
    code = map_status_to_code(exc.status_code)
    message = f"Slide API returned {', '.join(exc.codes) or exc.status_code}"
    return envelope(code, message)
