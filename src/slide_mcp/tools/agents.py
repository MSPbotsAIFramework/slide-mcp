"""Slide agents: the protected systems backing up to Slide (one per client)."""

from __future__ import annotations

from typing import Any, Callable

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from ..api_client import SlideAPIError, SlideClient
from ..errors import from_slide_error, not_configured
from ..responses import clamp_limit, item_result, list_result


def _shape_agent(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "agent_id": item.get("agent_id"),
        "client_id": item.get("client_id"),
        "device_id": item.get("device_id"),
        "display_name": item.get("display_name"),
        "hostname": item.get("hostname"),
        "platform": item.get("platform"),
        "last_seen_at": item.get("last_seen_at"),
        "backup_schedule_active": item.get("backup_schedule_active"),
        "backup_paused_indefinite": item.get("backup_paused_indefinite"),
        "backup_paused_until": item.get("backup_paused_until"),
    }


def register(mcp: FastMCP, client_factory: Callable[[], SlideClient | None]) -> None:
    @mcp.tool(
        description=(
            "List protected systems (agents) in Slide, optionally scoped to one client.\n"
            "Args: client_id (optional), limit (max 50, default 10), offset for "
            "pagination. Returns whether each agent's backup schedule is active or paused."
        ),
        annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    )
    async def slide_list_agents(
        client_id: str | None = None, limit: int = 10, offset: int = 0
    ) -> str:
        client = client_factory()
        if client is None:
            return not_configured("Slide API key is not available for this request")
        try:
            raw = await client.list_agents(
                client_id=client_id, limit=clamp_limit(limit), offset=max(0, offset)
            )
        except SlideAPIError as exc:
            return from_slide_error(exc)
        finally:
            await client.aclose()
        return list_result(raw, shape=_shape_agent)

    @mcp.tool(
        description="Get one Slide agent (protected system) by id. Args: agent_id (required).",
        annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    )
    async def slide_get_agent(agent_id: str) -> str:
        client = client_factory()
        if client is None:
            return not_configured("Slide API key is not available for this request")
        try:
            raw = await client.get_agent(agent_id)
        except SlideAPIError as exc:
            return from_slide_error(exc)
        finally:
            await client.aclose()
        return item_result(raw, shape=_shape_agent)
