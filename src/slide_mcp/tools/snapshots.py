"""Slide snapshots: recovery points and their integrity verification results."""

from __future__ import annotations

from typing import Any, Callable

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from ..api_client import SlideAPIError, SlideClient
from ..errors import from_slide_error, not_configured
from ..responses import clamp_limit, item_result, list_result


def _shape_snapshot(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "snapshot_id": item.get("snapshot_id"),
        "agent_id": item.get("agent_id"),
        "backup_started_at": item.get("backup_started_at"),
        "backup_ended_at": item.get("backup_ended_at"),
        "deleted": item.get("deleted"),
        "verify_boot_status": item.get("verify_boot_status"),
        "verify_fs_status": item.get("verify_fs_status"),
        "verify_service_status": item.get("verify_service_status"),
    }


def register(mcp: FastMCP, client_factory: Callable[[], SlideClient | None]) -> None:
    @mcp.tool(
        description=(
            "List recovery points (snapshots), optionally scoped to one agent.\n"
            "Args: agent_id (optional), limit (max 50, default 10), offset for pagination."
        ),
        annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    )
    async def slide_list_snapshots(
        agent_id: str | None = None, limit: int = 10, offset: int = 0
    ) -> str:
        client = client_factory()
        if client is None:
            return not_configured("Slide API key is not available for this request")
        try:
            raw = await client.list_snapshots(
                agent_id=agent_id, limit=clamp_limit(limit), offset=max(0, offset)
            )
        except SlideAPIError as exc:
            return from_slide_error(exc)
        finally:
            await client.aclose()
        return list_result(raw, shape=_shape_snapshot)

    @mcp.tool(
        description=(
            "Get one snapshot's integrity verification results: boot, filesystem, "
            "service status.\nArgs: snapshot_id (required)."
        ),
        annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    )
    async def slide_get_snapshot(snapshot_id: str) -> str:
        client = client_factory()
        if client is None:
            return not_configured("Slide API key is not available for this request")
        try:
            raw = await client.get_snapshot(snapshot_id)
        except SlideAPIError as exc:
            return from_slide_error(exc)
        finally:
            await client.aclose()
        return item_result(raw, shape=_shape_snapshot)
