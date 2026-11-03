"""Entry point: run the Starlette app (health probe + mounted MCP app) under uvicorn."""

from __future__ import annotations

import uvicorn

from .config import settings
from .server import create_app

app = create_app()


def main() -> None:
    uvicorn.run(app, host=settings.mcp_http_host, port=settings.mcp_http_port, log_level="info")


if __name__ == "__main__":
    main()
