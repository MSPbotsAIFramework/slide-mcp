"""Missing-header 401 (TC9) and per-request credential isolation under
concurrency (TC13, AC11) — the two things SOP §3.3/§3.4 call out as the
highest-risk part of this contract.
"""

from __future__ import annotations

import asyncio

import httpx
import respx
from asgi_lifespan import LifespanManager
from httpx import ASGITransport

from slide_mcp.server import CREDENTIAL_HEADER_NAME, create_app


async def test_missing_header_returns_structured_401():
    app = create_app()
    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/mcp",
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                },
                json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            )
    assert resp.status_code == 401
    body = resp.json()
    assert body["error"]["code"] == "unauthorized"
    assert CREDENTIAL_HEADER_NAME in body["error"]["message"]


async def test_concurrent_requests_do_not_share_credential_context():
    seen_tokens: list[str] = []

    def _record_and_respond(request: httpx.Request) -> httpx.Response:
        seen_tokens.append(request.headers.get("authorization", ""))
        return httpx.Response(200, json={"data": [], "pagination": {}})

    app = create_app()

    async with LifespanManager(app):
        transport = ASGITransport(app=app)

        with respx.mock(base_url="https://api.slide.tech") as rsx:
            rsx.get("/v1/client").mock(side_effect=_record_and_respond)

            async def call(token: str) -> httpx.Response:
                async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                    return await client.post(
                        "/mcp",
                        headers={
                            "Content-Type": "application/json",
                            "Accept": "application/json, text/event-stream",
                            CREDENTIAL_HEADER_NAME: token,
                        },
                        json={
                            "jsonrpc": "2.0",
                            "id": 1,
                            "method": "tools/call",
                            "params": {"name": "slide_list_clients", "arguments": {}},
                        },
                    )

            responses = await asyncio.gather(call("token-A"), call("token-B"))

    for resp in responses:
        assert resp.status_code == 200

    assert len(seen_tokens) == 2
    assert set(seen_tokens) == {"Bearer token-A", "Bearer token-B"}
