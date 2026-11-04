"""Thin async wrapper around the Slide REST API (https://docs.slide.tech/api/).

One instance is built per MCP request (see server.py's client_factory), bound to that
request's own bearer token. Nothing here is cached or shared across requests (SOP §3.4).
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any

import httpx

from .error_codes import map_status_to_code

CONNECT_TIMEOUT_S = 5.0
READ_TIMEOUT_S = 30.0
MAX_RETRIES = 3
TOTAL_BUDGET_S = 120.0

logger = logging.getLogger("slide_mcp.api_client")


def _log_call(
    *,
    request_id: str,
    tool: str,
    method: str,
    path: str,
    params: dict[str, Any],
    status_code: int,
    attempts: int,
    duration_s: float,
    error_code: str | None,
) -> None:
    """One structured line per outbound Slide request (SOP §6).

    `path`/`params` only ever carry Slide resource ids and list filters (limit,
    offset, client_id, etc.) -- never the bearer token, which lives solely in the
    client's headers and is never threaded through here. On failure this logs our
    own mapped `error_code`, never the raw vendor `message`/`details`.
    """
    record = {
        "event": "slide_api_call",
        "request_id": request_id,
        "tool": tool,
        "method": method,
        "path": path,
        "params": params,
        "status_code": status_code,
        "attempts": attempts,
        "duration_ms": round(duration_s * 1000, 1),
        "error_code": error_code,
    }
    line = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
    if error_code is not None:
        logger.warning(line)
    else:
        logger.info(line)


class SlideAPIError(Exception):
    """Raised for any Slide HTTP response >= 400, or an unreachable upstream."""

    def __init__(self, status_code: int, codes: list[str], message: str) -> None:
        self.status_code = status_code
        self.codes = codes
        self.message = message
        super().__init__(f"Slide API error {status_code}: {codes} {message}")


class SlideClient:
    """One Slide API client per request, scoped to one caller's bearer token."""

    def __init__(self, token: str, base_url: str) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=httpx.Timeout(connect=CONNECT_TIMEOUT_S, read=READ_TIMEOUT_S, write=READ_TIMEOUT_S, pool=READ_TIMEOUT_S),
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _request(
        self, method: str, path: str, *, tool: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        params = {k: v for k, v in (params or {}).items() if v is not None}
        loop = asyncio.get_event_loop()
        started = loop.time()
        deadline = started + TOTAL_BUDGET_S
        attempt = 0
        last_exc: Exception | None = None
        request_id = uuid.uuid4().hex[:12]

        while True:
            attempt += 1
            try:
                resp = await self._client.request(method, path, params=params)
            except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout, httpx.TransportError) as exc:
                last_exc = exc
                if attempt > MAX_RETRIES or loop.time() >= deadline:
                    _log_call(
                        request_id=request_id,
                        tool=tool,
                        method=method,
                        path=path,
                        params=params,
                        status_code=0,
                        attempts=attempt,
                        duration_s=loop.time() - started,
                        error_code="upstream_error",
                    )
                    raise SlideAPIError(0, ["upstream_unreachable"], f"Could not reach Slide API: {exc}") from exc
                await asyncio.sleep(min(2 ** (attempt - 1), max(0.0, deadline - loop.time())))
                continue

            if resp.status_code < 400:
                _log_call(
                    request_id=request_id,
                    tool=tool,
                    method=method,
                    path=path,
                    params=params,
                    status_code=resp.status_code,
                    attempts=attempt,
                    duration_s=loop.time() - started,
                    error_code=None,
                )
                if resp.status_code == 204 or not resp.content:
                    return {}
                return resp.json()

            if resp.status_code in (429, 500, 502, 503, 504) and attempt <= MAX_RETRIES and loop.time() < deadline:
                retry_after = _parse_retry_after(resp.headers.get("Retry-After"))
                delay = retry_after if retry_after is not None else min(2 ** (attempt - 1), 10.0)
                remaining = deadline - loop.time()
                if remaining <= 0:
                    pass
                else:
                    await asyncio.sleep(min(delay, remaining))
                    continue

            codes, message = _parse_error_body(resp)
            _log_call(
                request_id=request_id,
                tool=tool,
                method=method,
                path=path,
                params=params,
                status_code=resp.status_code,
                attempts=attempt,
                duration_s=loop.time() - started,
                error_code=map_status_to_code(resp.status_code),
            )
            raise SlideAPIError(resp.status_code, codes, message)

        # Unreachable, but keeps type checkers happy if the loop above is ever restructured.
        raise SlideAPIError(0, ["upstream_unreachable"], str(last_exc) if last_exc else "unknown error")

    # -- Clients --------------------------------------------------------------
    async def list_clients(self, *, limit: int, offset: int) -> dict[str, Any]:
        return await self._request(
            "GET", "/v1/client", tool="slide_list_clients", params={"limit": limit, "offset": offset}
        )

    # -- Agents -----------------------------------------------------------------
    async def list_agents(self, *, client_id: str | None, limit: int, offset: int) -> dict[str, Any]:
        return await self._request(
            "GET",
            "/v1/agent",
            tool="slide_list_agents",
            params={"client_id": client_id, "limit": limit, "offset": offset},
        )

    async def get_agent(self, agent_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/v1/agent/{agent_id}", tool="slide_get_agent")

    # -- Devices ------------------------------------------------------------
    async def list_devices(self, *, client_id: str | None, limit: int, offset: int) -> dict[str, Any]:
        return await self._request(
            "GET",
            "/v1/device",
            tool="slide_list_devices",
            params={"client_id": client_id, "limit": limit, "offset": offset},
        )

    async def get_device(self, device_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/v1/device/{device_id}", tool="slide_get_device")

    # -- Backups ------------------------------------------------------------
    async def list_backups(
        self,
        *,
        agent_id: str | None,
        device_id: str | None,
        snapshot_id: str | None,
        limit: int,
        offset: int,
    ) -> dict[str, Any]:
        return await self._request(
            "GET",
            "/v1/backup",
            tool="slide_list_backups",
            params={
                "agent_id": agent_id,
                "device_id": device_id,
                "snapshot_id": snapshot_id,
                "limit": limit,
                "offset": offset,
            },
        )

    async def get_backup(self, backup_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/v1/backup/{backup_id}", tool="slide_get_backup")

    # -- Snapshots ----------------------------------------------------------
    async def list_snapshots(self, *, agent_id: str | None, limit: int, offset: int) -> dict[str, Any]:
        return await self._request(
            "GET",
            "/v1/snapshot",
            tool="slide_list_snapshots",
            params={"agent_id": agent_id, "limit": limit, "offset": offset},
        )

    async def get_snapshot(self, snapshot_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/v1/snapshot/{snapshot_id}", tool="slide_get_snapshot")

    # -- Alerts ---------------------------------------------------------------
    async def list_alerts(
        self, *, agent_id: str | None, resolved: bool | None, limit: int, offset: int
    ) -> dict[str, Any]:
        return await self._request(
            "GET",
            "/v1/alert",
            tool="slide_list_alerts",
            params={"agent_id": agent_id, "resolved": resolved, "limit": limit, "offset": offset},
        )

    async def get_alert(self, alert_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/v1/alert/{alert_id}", tool="slide_get_alert")

    # -- Audit ----------------------------------------------------------------
    async def list_audit_logs(self, *, limit: int, offset: int) -> dict[str, Any]:
        return await self._request(
            "GET", "/v1/audit", tool="slide_list_audit_logs", params={"limit": limit, "offset": offset}
        )


def _parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None


def _parse_error_body(resp: httpx.Response) -> tuple[list[str], str]:
    try:
        body = resp.json()
    except ValueError:
        return ([str(resp.status_code)], f"Slide API returned HTTP {resp.status_code}")
    codes = body.get("codes") if isinstance(body, dict) else None
    message = body.get("message") if isinstance(body, dict) else None
    if not isinstance(codes, list):
        codes = [str(resp.status_code)]
    if not isinstance(message, str):
        message = f"Slide API returned HTTP {resp.status_code}"
    return (codes, message)
