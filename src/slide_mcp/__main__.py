"""Entry point: run the Starlette app (health probe + mounted MCP app) under uvicorn."""

from __future__ import annotations

import logging

import uvicorn

from .config import settings
from .server import create_app

app = create_app()


def main() -> None:
    # Our own structured per-call logs (api_client.py, SOP §6) are plain JSON lines
    # on their own logger -- make sure they actually reach stdout instead of being
    # dropped by Python's default "no handler configured" behavior. uvicorn's
    # log_level="info" below only configures uvicorn's own loggers, not this one.
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    uvicorn.run(app, host=settings.mcp_http_host, port=settings.mcp_http_port, log_level="info")


if __name__ == "__main__":
    main()
