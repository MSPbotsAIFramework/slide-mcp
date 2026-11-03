"""Shared helpers for shaping tool results (SOP §2.5: token economy).

Every list tool returns at most `limit` items plus a `has_more` signal derived from
Slide's own `pagination.next_offset`; every tool's JSON is serialized compactly
(no indentation, `ensure_ascii=False`) and capped at 20000 characters.
"""

from __future__ import annotations

import json
from typing import Any, Callable

DEFAULT_LIMIT = 10
MAX_LIMIT = 50
MAX_RESULT_CHARS = 20000


def clamp_limit(limit: int | None) -> int:
    if limit is None:
        return DEFAULT_LIMIT
    return max(1, min(limit, MAX_LIMIT))


def dump(payload: dict[str, Any]) -> str:
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    if len(text) <= MAX_RESULT_CHARS:
        return text
    # Degrade gracefully: if a single tool call's JSON would exceed the cap (an
    # unusually wide `data` list), drop trailing items until it fits and say so.
    data = payload.get("data")
    if isinstance(data, list) and data:
        trimmed = dict(payload)
        trimmed["has_more"] = True
        trimmed["truncated"] = True
        while data and len(
            json.dumps({**trimmed, "data": data}, ensure_ascii=False, separators=(",", ":"))
        ) > MAX_RESULT_CHARS:
            data = data[:-1]
        trimmed["data"] = data
        return json.dumps(trimmed, ensure_ascii=False, separators=(",", ":"))
    return text[:MAX_RESULT_CHARS]


def list_result(
    raw: dict[str, Any], *, shape: Callable[[dict[str, Any]], dict[str, Any]]
) -> str:
    items = [shape(item) for item in raw.get("data", [])]
    next_offset = (raw.get("pagination") or {}).get("next_offset")
    payload: dict[str, Any] = {"data": items, "has_more": next_offset is not None}
    if next_offset is not None:
        payload["next_offset"] = next_offset
    return dump(payload)


def item_result(raw: dict[str, Any], *, shape: Callable[[dict[str, Any]], dict[str, Any]]) -> str:
    return dump(shape(raw))
