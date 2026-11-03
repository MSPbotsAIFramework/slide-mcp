"""FastMCP factory and the request-level credential middleware.

Credential handling follows SOP §3: the Slide API key is read from the
``X-Slide-Api-Key`` request header into a ``contextvars.ContextVar``, reset in a
``finally`` block, and never stored anywhere else (no env var fallback, no
module-level cache, no cross-request reuse).
"""

from __future__ import annotations

import contextvars
import json

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route
from starlette.types import ASGIApp, Receive, Scope, Send

from .api_client import SlideClient
from .config import settings

CREDENTIAL_HEADER_NAME = "X-Slide-Api-Key"
_CREDENTIAL_HEADER_BYTES = CREDENTIAL_HEADER_NAME.lower().encode("ascii")

_current_token: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "slide_api_key", default=None
)

INSTRUCTIONS = (
    "Slide BCDR status connector. Use these tools to review the current state of an "
    "MSP's Slide-protected estate: which clients/sites and agents (protected systems) "
    "exist, whether a device's (Slide appliance) backup schedule is active, whether "
    "recent backup runs succeeded, whether snapshots (recovery points) pass Slide's "
    "integrity verification, and which alerts are open. Typical flow: "
    "slide_list_clients -> slide_list_agents(client_id=...) -> "
    "slide_list_backups(agent_id=...) / slide_get_snapshot(snapshot_id=...) to check a "
    "specific recovery point -> slide_list_alerts() for anything needing attention. "
    "All tools are read-only; no backup/restore operations are started from here."
)


def client_factory() -> SlideClient | None:
    """Build a Slide API client bound to the current request's credential.

    Returns None if no token is in context (should not normally happen — the
    middleware already rejects un-credentialed requests before any tool runs);
    tools treat a None client as a `not_configured` error, never a crash.
    """
    token = _current_token.get()
    if not token:
        return None
    return SlideClient(token=token, base_url=settings.slide_base_url)


def _missing_header_response() -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content={
            "error": {
                "code": "unauthorized",
                "message": f"Missing required header: {CREDENTIAL_HEADER_NAME}",
                "retryable": False,
            }
        },
    )


class CredentialMiddleware:
    """Raw ASGI middleware — deliberately not BaseHTTPMiddleware, so Streamable
    HTTP's streaming responses are never buffered or rewritten.
    """

    def __init__(self, app: ASGIApp, guarded_path: str) -> None:
        self._app = app
        self._guarded_path = guarded_path

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] != self._guarded_path:
            await self._app(scope, receive, send)
            return

        headers = dict(scope.get("headers") or [])
        raw_token = headers.get(_CREDENTIAL_HEADER_BYTES)
        if not raw_token:
            await _missing_header_response()(scope, receive, send)
            return

        token = raw_token.decode("utf-8", errors="replace").strip()
        if not token:
            await _missing_header_response()(scope, receive, send)
            return

        reset_token = _current_token.set(token)
        try:
            await self._app(scope, receive, send)
        finally:
            _current_token.reset(reset_token)


async def _health(_request: Request) -> JSONResponse:
    # Pure local probe — never calls the Slide API (SOP §1.1).
    return JSONResponse({"status": "ok"})


def create_mcp_server() -> FastMCP:
    mcp = FastMCP(
        name="slide-mcp",
        instructions=INSTRUCTIONS,
        host=settings.mcp_http_host,
        port=settings.mcp_http_port,
        stateless_http=True,
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )

    from .tools import agents, alerts, audit, backups, clients, devices, snapshots

    clients.register(mcp, client_factory)
    agents.register(mcp, client_factory)
    devices.register(mcp, client_factory)
    backups.register(mcp, client_factory)
    snapshots.register(mcp, client_factory)
    alerts.register(mcp, client_factory)
    audit.register(mcp, client_factory)

    return mcp


def create_app() -> Starlette:
    mcp = create_mcp_server()
    mcp_asgi_app = mcp.streamable_http_app()

    app = Starlette(
        routes=[
            Route("/health", _health),
            Mount("/", app=mcp_asgi_app),
        ],
        # The Streamable HTTP sub-app owns its own session-manager lifespan;
        # Starlette's Mount does NOT run a mounted sub-app's lifespan on its own,
        # so it must be attached to the outer app explicitly (SOP §7).
        lifespan=mcp_asgi_app.router.lifespan_context,
    )
    app = CredentialMiddleware(app, guarded_path=mcp.settings.streamable_http_path)
    return app  # type: ignore[return-value]


def envelope_not_configured() -> str:
    return json.dumps(
        {
            "error": {
                "code": "not_configured",
                "message": f"No {CREDENTIAL_HEADER_NAME} in request context",
                "retryable": False,
            }
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
