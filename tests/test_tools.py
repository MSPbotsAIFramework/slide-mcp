"""tools/list snapshot + per-tool status-code -> error-code mapping + the
auto test cases from docs/tickets/PRD-21274.ac.json (TC1, TC2, TC3, TC5, TC6,
TC7, TC8, TC10, TC11, TC12).
"""

from __future__ import annotations

import httpx
import pytest
import respx

from .conftest import call_tool, credential

EXPECTED_TOOLS = {
    "slide_list_clients": set(),
    "slide_list_agents": set(),
    "slide_get_agent": {"agent_id"},
    "slide_list_devices": set(),
    "slide_get_device": {"device_id"},
    "slide_list_backups": set(),
    "slide_get_backup": {"backup_id"},
    "slide_list_snapshots": set(),
    "slide_get_snapshot": {"snapshot_id"},
    "slide_list_alerts": set(),
    "slide_get_alert": {"alert_id"},
    "slide_list_audit_logs": set(),
}


async def test_tools_list_snapshot(mcp):
    tools = await mcp.list_tools()
    assert {t.name for t in tools} == set(EXPECTED_TOOLS)
    assert len(tools) == 12
    for tool in tools:
        required = set(tool.inputSchema.get("required", []))
        assert required == EXPECTED_TOOLS[tool.name], tool.name
        assert tool.annotations is not None and tool.annotations.readOnlyHint is True
        # SOP §2.2: first line <=100 chars, whole description <=500 chars.
        first_line = (tool.description or "").splitlines()[0]
        assert len(first_line) <= 100
        assert len(tool.description or "") <= 500


async def test_list_clients_returns_id_and_name(mcp):
    with respx.mock(base_url="https://api.slide.tech") as rsx:
        rsx.get("/v1/client").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {"client_id": "c_1", "name": "Acme Co", "comments": "internal note"}
                    ],
                    "pagination": {},
                },
            )
        )
        with credential("tok"):
            result = await call_tool(mcp, "slide_list_clients")
    assert result["data"] == [{"client_id": "c_1", "name": "Acme Co"}]
    assert result["has_more"] is False


async def test_list_agents_reports_backup_schedule_state(mcp):
    with respx.mock(base_url="https://api.slide.tech") as rsx:
        rsx.get("/v1/agent").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "agent_id": "a_1",
                            "client_id": "c_1",
                            "device_id": "d_1",
                            "display_name": "WEB01",
                            "hostname": "web01.acme.local",
                            "platform": "windows",
                            "last_seen_at": "2026-11-01T00:00:00Z",
                            "backup_schedule_active": True,
                            "backup_paused_indefinite": False,
                            "backup_paused_until": None,
                        }
                    ],
                    "pagination": {},
                },
            )
        )
        with credential("tok"):
            result = await call_tool(mcp, "slide_list_agents", {"client_id": "c_1"})
    agent = result["data"][0]
    assert agent["agent_id"] == "a_1"
    assert agent["display_name"] == "WEB01"
    assert agent["hostname"] == "web01.acme.local"
    assert agent["platform"] == "windows"
    assert agent["last_seen_at"] == "2026-11-01T00:00:00Z"
    assert agent["backup_schedule_active"] is True
    assert agent["backup_paused_indefinite"] is False


async def test_list_backups_surfaces_failure_detail(mcp):
    with respx.mock(base_url="https://api.slide.tech") as rsx:
        rsx.get("/v1/backup").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "backup_id": "b_1",
                            "agent_id": "a_1",
                            "snapshot_id": None,
                            "started_at": "2026-11-01T02:00:00Z",
                            "ended_at": "2026-11-01T02:05:00Z",
                            "status": "failed",
                            "error_code": 42,
                            "error_message": "disk full",
                        }
                    ],
                    "pagination": {},
                },
            )
        )
        with credential("tok"):
            result = await call_tool(mcp, "slide_list_backups", {"agent_id": "a_1"})
    backup = result["data"][0]
    assert backup["status"] == "failed"
    assert backup["error_code"] == 42
    assert backup["error_message"] == "disk full"


async def test_get_device_returns_health_fields(mcp):
    with respx.mock(base_url="https://api.slide.tech") as rsx:
        rsx.get("/v1/device/d_1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "device_id": "d_1",
                    "client_id": "c_1",
                    "display_name": "SLIDE-01",
                    "hostname": "slide-01",
                    "service_status": "online",
                    "last_seen_at": "2026-11-02T00:00:00Z",
                    "storage_used_bytes": 1000,
                    "storage_total_bytes": 2000,
                },
            )
        )
        with credential("tok"):
            result = await call_tool(mcp, "slide_get_device", {"device_id": "d_1"})
    assert result["service_status"] == "online"
    assert result["last_seen_at"] == "2026-11-02T00:00:00Z"
    assert result["storage_used_bytes"] == 1000
    assert result["storage_total_bytes"] == 2000


async def test_list_alerts_default_and_resolved_filter(mcp):
    with respx.mock(base_url="https://api.slide.tech") as rsx:
        unresolved_route = rsx.get("/v1/alert", params={"resolved": "false"}).mock(
            return_value=httpx.Response(
                200, json={"data": [{"alert_id": "al_1", "resolved": False}], "pagination": {}}
            )
        )
        resolved_route = rsx.get("/v1/alert", params={"resolved": "true"}).mock(
            return_value=httpx.Response(
                200, json={"data": [{"alert_id": "al_2", "resolved": True}], "pagination": {}}
            )
        )
        with credential("tok"):
            default_result = await call_tool(mcp, "slide_list_alerts")
            resolved_result = await call_tool(mcp, "slide_list_alerts", {"resolved": True})
    assert unresolved_route.called
    assert resolved_route.called
    assert default_result["data"] == [{"alert_id": "al_1", "agent_id": None, "device_id": None,
                                        "alert_type": None, "created_at": None, "resolved": False,
                                        "resolved_at": None, "resolved_by": None}]
    assert resolved_result["data"][0]["alert_id"] == "al_2"
    assert resolved_result["data"][0]["resolved"] is True


async def test_list_alerts_empty_is_not_an_error(mcp):
    with respx.mock(base_url="https://api.slide.tech") as rsx:
        rsx.get("/v1/alert").mock(
            return_value=httpx.Response(200, json={"data": [], "pagination": {}})
        )
        with credential("tok"):
            result = await call_tool(mcp, "slide_list_alerts", {"agent_id": "a_nobody"})
    assert result == {"data": [], "has_more": False}
    assert "error" not in result


async def test_get_snapshot_returns_verification_fields(mcp):
    with respx.mock(base_url="https://api.slide.tech") as rsx:
        rsx.get("/v1/snapshot/s_1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "snapshot_id": "s_1",
                    "agent_id": "a_1",
                    "verify_boot_status": "passed",
                    "verify_fs_status": "passed",
                    "verify_service_status": "passed",
                },
            )
        )
        with credential("tok"):
            result = await call_tool(mcp, "slide_get_snapshot", {"snapshot_id": "s_1"})
    assert result["verify_boot_status"] == "passed"
    assert result["verify_fs_status"] == "passed"
    assert result["verify_service_status"] == "passed"


async def test_upstream_401_does_not_leak_credential_or_body(mcp):
    secret_token = "sk_super_secret_value"
    with respx.mock(base_url="https://api.slide.tech") as rsx:
        rsx.get("/v1/client").mock(
            return_value=httpx.Response(
                401,
                json={
                    "codes": ["err_unauthorized"],
                    "message": f"token {secret_token} is invalid",
                    "details": [],
                },
            )
        )
        with credential(secret_token):
            result = await call_tool(mcp, "slide_list_clients")
    assert result["error"]["code"] == "unauthorized"
    assert secret_token not in result["error"]["message"]
    assert "is invalid" not in result["error"]["message"]
    assert result["error"]["retryable"] is False


async def test_list_pagination_bounds_results(mcp):
    all_items = [{"client_id": f"c_{i}", "name": f"Client {i}"} for i in range(60)]

    def _fake_slide_server(request: httpx.Request) -> httpx.Response:
        # Mirrors Slide's own behaviour: it never returns more than `limit`
        # items, regardless of how many exist (mimics the vendor's own cap).
        params = dict(httpx.QueryParams(request.url.query))
        limit = int(params.get("limit", 10))
        offset = int(params.get("offset", 0))
        page = all_items[offset : offset + limit]
        next_offset = offset + limit if offset + limit < len(all_items) else None
        pagination = {"next_offset": next_offset} if next_offset is not None else {}
        return httpx.Response(200, json={"data": page, "pagination": pagination})

    with respx.mock(base_url="https://api.slide.tech") as rsx:
        rsx.get("/v1/client").mock(side_effect=_fake_slide_server)
        with credential("tok"):
            result = await call_tool(mcp, "slide_list_clients", {"limit": 200})
    # limit is clamped to the 50 hard cap before the call is even made, so the
    # mocked "server" (which itself never exceeds the requested limit) never
    # receives or returns more than 50 — the full 60-item set is never seen.
    assert len(result["data"]) == 50
    assert result["has_more"] is True
    assert result["next_offset"] == 50


async def test_429_maps_to_rate_limited(mcp):
    with respx.mock(base_url="https://api.slide.tech") as rsx:
        rsx.get("/v1/client").mock(
            side_effect=[
                httpx.Response(429, headers={"Retry-After": "0"}, json={"codes": ["err_rate_limited"], "message": "slow down"}),
                httpx.Response(429, headers={"Retry-After": "0"}, json={"codes": ["err_rate_limited"], "message": "slow down"}),
                httpx.Response(429, headers={"Retry-After": "0"}, json={"codes": ["err_rate_limited"], "message": "slow down"}),
                httpx.Response(429, headers={"Retry-After": "0"}, json={"codes": ["err_rate_limited"], "message": "slow down"}),
            ]
        )
        with credential("tok"):
            result = await call_tool(mcp, "slide_list_clients")
    assert result["error"]["code"] == "rate_limited"
    assert result["error"]["retryable"] is True


async def test_503_maps_to_upstream_error(mcp):
    with respx.mock(base_url="https://api.slide.tech") as rsx:
        rsx.get("/v1/client").mock(
            side_effect=[httpx.Response(503, json={"codes": ["err_unavailable"], "message": "down"})] * 4
        )
        with credential("tok"):
            result = await call_tool(mcp, "slide_list_clients")
    assert result["error"]["code"] == "upstream_error"
    assert result["error"]["retryable"] is True
