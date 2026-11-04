"""HTTP status -> MCP error-code mapping.

Shared by errors.py (the client-facing error envelope, SOP §4.2) and api_client.py
(structured call logging, SOP §6) so the two never drift apart. Single source of
truth for "what does a Slide HTTP status mean in our own error taxonomy".
"""

from __future__ import annotations

_ERROR_CODE_BY_STATUS: dict[int, str] = {
    400: "invalid_argument",
    401: "unauthorized",
    403: "unauthorized",
    404: "not_found",
    422: "invalid_argument",
    429: "rate_limited",
}


def map_status_to_code(status_code: int) -> str:
    """Map a Slide HTTP status (or 0 for an unreachable upstream) to our error code."""
    if status_code == 0 or status_code >= 500:
        return "upstream_error"
    return _ERROR_CODE_BY_STATUS.get(status_code, "upstream_error")
