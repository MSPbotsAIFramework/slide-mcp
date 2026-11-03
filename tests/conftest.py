from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Any, Iterator

import pytest

from slide_mcp.server import _current_token, create_mcp_server


@pytest.fixture
def mcp():
    return create_mcp_server()


@contextmanager
def credential(token: str | None) -> Iterator[None]:
    """Simulate the middleware having put `token` into the request context."""
    reset = _current_token.set(token)
    try:
        yield
    finally:
        _current_token.reset(reset)


async def call_tool(mcp, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    """Call a registered tool and parse its JSON string result."""
    content, _structured = await mcp.call_tool(name, arguments or {})
    text = content[0].text
    return json.loads(text)
