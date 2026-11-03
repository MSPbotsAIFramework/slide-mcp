"""Slide clients: the MSP's end-customers/sites onboarded in Slide."""

from __future__ import annotations

from typing import Any, Callable

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from ..api_client import SlideAPIError, SlideClient
from ..errors import from_slide_error, not_configured
from ..responses import clamp_limit, list_result


def _shape_client(item: dict[str, Any]) -> dict[str, Any]:
    return {"client_id": item.get("client_id"), "name": item.get("name")}


def register(mcp: FastMCP, client_factory: Callable[[], SlideClient | None]) -> None:
    @mcp.tool(
        description=(
            "List the MSP's end-customers/sites onboarded in Slide.\n"
            "Args: limit (max 50, default 10), offset for pagination."
        ),
        annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True),
    )
    async def slide_list_clients(limit: int = 10, offset: int = 0) -> str:
        client = client_factory()
        if client is None:
            return not_configured("Slide API key is not available for this request")
        try:
            raw = await client.list_clients(limit=clamp_limit(limit), offset=max(0, offset))
        except SlideAPIError as exc:
            return from_slide_error(exc)
        finally:
            await client.aclose()
        return list_result(raw, shape=_shape_client)
