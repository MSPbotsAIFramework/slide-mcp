"""Slide audit log: read-only activity trail. List-only — the single-item
Slide endpoint adds no field the list response doesn't already carry, so no
get-by-id tool is exposed (token economy, SOP §2.5).
"""

from __future__ import annotations

from typing import Any, Callable

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from ..api_client import SlideAPIError, SlideClient
from ..errors import from_slide_error, not_configured
from ..responses import clamp_limit, list_result


def _shape_audit_entry(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "audit_id": item.get("audit_id"),
        "audit_time": item.get("audit_time"),
        "action": item.get("action"),
        "description": item.get("description"),
        "resource_type": item.get("resource_type"),
        "resource_id": item.get("resource_id"),
        "client_id": item.get("client_id"),
        "user_id": item.get("user_id"),
        "system": item.get("system"),
        "source": item.get("source"),
    }


def register(mcp: FastMCP, client_factory: Callable[[], SlideClient | None]) -> None:
    @mcp.tool(
        description=(
            "List audit log entries (activity trail: who did what, when).\n"
            "Args: limit (max 50, default 10), offset for pagination."
        ),
        annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    )
    async def slide_list_audit_logs(limit: int = 10, offset: int = 0) -> str:
        client = client_factory()
        if client is None:
            return not_configured("Slide API key is not available for this request")
        try:
            raw = await client.list_audit_logs(limit=clamp_limit(limit), offset=max(0, offset))
        except SlideAPIError as exc:
            return from_slide_error(exc)
        finally:
            await client.aclose()
        return list_result(raw, shape=_shape_audit_entry)
