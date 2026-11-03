"""Slide backups: individual backup runs for an agent."""

from __future__ import annotations

from typing import Any, Callable

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from ..api_client import SlideAPIError, SlideClient
from ..errors import from_slide_error, not_configured
from ..responses import clamp_limit, item_result, list_result


def _shape_backup(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "backup_id": item.get("backup_id"),
        "agent_id": item.get("agent_id"),
        "snapshot_id": item.get("snapshot_id"),
        "started_at": item.get("started_at"),
        "ended_at": item.get("ended_at"),
        "status": item.get("status"),
        "error_code": item.get("error_code"),
        "error_message": item.get("error_message"),
    }


def register(mcp: FastMCP, client_factory: Callable[[], SlideClient | None]) -> None:
    @mcp.tool(
        description=(
            "List backup runs, optionally scoped to one agent, device, or snapshot.\n"
            "Args: agent_id, device_id, snapshot_id (all optional), limit (max 50, "
            "default 10), offset for pagination. A failed run carries an error_code/message."
        ),
        annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    )
    async def slide_list_backups(
        agent_id: str | None = None,
        device_id: str | None = None,
        snapshot_id: str | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> str:
        client = client_factory()
        if client is None:
            return not_configured("Slide API key is not available for this request")
        try:
            raw = await client.list_backups(
                agent_id=agent_id,
                device_id=device_id,
                snapshot_id=snapshot_id,
                limit=clamp_limit(limit),
                offset=max(0, offset),
            )
        except SlideAPIError as exc:
            return from_slide_error(exc)
        finally:
            await client.aclose()
        return list_result(raw, shape=_shape_backup)

    @mcp.tool(
        description=(
            "Get one backup run: start/end time, status, error detail if failed.\n"
            "Args: backup_id (required)."
        ),
        annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    )
    async def slide_get_backup(backup_id: str) -> str:
        client = client_factory()
        if client is None:
            return not_configured("Slide API key is not available for this request")
        try:
            raw = await client.get_backup(backup_id)
        except SlideAPIError as exc:
            return from_slide_error(exc)
        finally:
            await client.aclose()
        return item_result(raw, shape=_shape_backup)
