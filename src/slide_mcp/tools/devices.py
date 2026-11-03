"""Slide devices: the physical/virtual Slide appliances themselves."""

from __future__ import annotations

from typing import Any, Callable

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from ..api_client import SlideAPIError, SlideClient
from ..errors import from_slide_error, not_configured
from ..responses import clamp_limit, item_result, list_result


def _shape_device(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "device_id": item.get("device_id"),
        "client_id": item.get("client_id"),
        "display_name": item.get("display_name"),
        "hostname": item.get("hostname"),
        "service_status": item.get("service_status"),
        "last_seen_at": item.get("last_seen_at"),
        "storage_used_bytes": item.get("storage_used_bytes"),
        "storage_total_bytes": item.get("storage_total_bytes"),
    }


def register(mcp: FastMCP, client_factory: Callable[[], SlideClient | None]) -> None:
    @mcp.tool(
        description=(
            "List Slide appliances (devices), optionally scoped to one client.\n"
            "Args: client_id (optional), limit (max 50, default 10), offset for pagination."
        ),
        annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    )
    async def slide_list_devices(
        client_id: str | None = None, limit: int = 10, offset: int = 0
    ) -> str:
        client = client_factory()
        if client is None:
            return not_configured("Slide API key is not available for this request")
        try:
            raw = await client.list_devices(
                client_id=client_id, limit=clamp_limit(limit), offset=max(0, offset)
            )
        except SlideAPIError as exc:
            return from_slide_error(exc)
        finally:
            await client.aclose()
        return list_result(raw, shape=_shape_device)

    @mcp.tool(
        description=(
            "Get one Slide appliance (device)'s status: service status, last-seen "
            "time, storage used/total.\nArgs: device_id (required)."
        ),
        annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    )
    async def slide_get_device(device_id: str) -> str:
        client = client_factory()
        if client is None:
            return not_configured("Slide API key is not available for this request")
        try:
            raw = await client.get_device(device_id)
        except SlideAPIError as exc:
            return from_slide_error(exc)
        finally:
            await client.aclose()
        return item_result(raw, shape=_shape_device)
