"""Slide alerts: conditions on agents/devices that need attention."""

from __future__ import annotations

from typing import Any, Callable

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from ..api_client import SlideAPIError, SlideClient
from ..errors import from_slide_error, not_configured
from ..responses import clamp_limit, item_result, list_result


def _shape_alert(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "alert_id": item.get("alert_id"),
        "agent_id": item.get("agent_id"),
        "device_id": item.get("device_id"),
        "alert_type": item.get("alert_type"),
        "created_at": item.get("created_at"),
        "resolved": item.get("resolved"),
        "resolved_at": item.get("resolved_at"),
        "resolved_by": item.get("resolved_by"),
    }


def register(mcp: FastMCP, client_factory: Callable[[], SlideClient | None]) -> None:
    @mcp.tool(
        description=(
            "List alerts; unresolved by default, resolved=true for resolved ones.\n"
            "Args: agent_id (optional), resolved (default false), limit (max 50, "
            "default 10), offset for pagination. No match returns an empty list, not an error."
        ),
        annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    )
    async def slide_list_alerts(
        agent_id: str | None = None,
        resolved: bool = False,
        limit: int = 10,
        offset: int = 0,
    ) -> str:
        client = client_factory()
        if client is None:
            return not_configured("Slide API key is not available for this request")
        try:
            raw = await client.list_alerts(
                agent_id=agent_id,
                resolved=resolved,
                limit=clamp_limit(limit),
                offset=max(0, offset),
            )
        except SlideAPIError as exc:
            return from_slide_error(exc)
        finally:
            await client.aclose()
        return list_result(raw, shape=_shape_alert)

    @mcp.tool(
        description="Get one alert by id. Args: alert_id (required).",
        annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    )
    async def slide_get_alert(alert_id: str) -> str:
        client = client_factory()
        if client is None:
            return not_configured("Slide API key is not available for this request")
        try:
            raw = await client.get_alert(alert_id)
        except SlideAPIError as exc:
            return from_slide_error(exc)
        finally:
            await client.aclose()
        return item_result(raw, shape=_shape_alert)
