"""Structured per-call logging (SOP §6), added in review round 1 rework.

Every outbound Slide request must leave one JSON log line on the
`slide_mcp.api_client` logger carrying the tool name, the Slide path, the
resulting status code, duration, and (on failure) our own mapped error code --
and must never carry the bearer token or the raw vendor message/details.
"""

from __future__ import annotations

import json
import logging

import httpx
import respx

from .conftest import call_tool, credential


async def test_successful_call_logs_tool_path_status_and_duration(caplog):
    from slide_mcp.server import create_mcp_server

    mcp = create_mcp_server()
    with caplog.at_level(logging.INFO, logger="slide_mcp.api_client"):
        with respx.mock(base_url="https://api.slide.tech") as rsx:
            rsx.get("/v1/client").mock(
                return_value=httpx.Response(200, json={"data": [], "pagination": {}})
            )
            with credential("tok"):
                await call_tool(mcp, "slide_list_clients", {"limit": 5, "offset": 0})

    records = [json.loads(r.message) for r in caplog.records if r.name == "slide_mcp.api_client"]
    assert len(records) == 1
    record = records[0]
    assert record["event"] == "slide_api_call"
    assert record["tool"] == "slide_list_clients"
    assert record["path"] == "/v1/client"
    assert record["status_code"] == 200
    assert record["error_code"] is None
    assert record["duration_ms"] >= 0
    assert record["params"] == {"limit": 5, "offset": 0}


async def test_failed_call_logs_mapped_error_code_never_the_credential(caplog):
    from slide_mcp.server import create_mcp_server

    mcp = create_mcp_server()
    secret_token = "sk_super_secret_value"
    with caplog.at_level(logging.INFO, logger="slide_mcp.api_client"):
        with respx.mock(base_url="https://api.slide.tech") as rsx:
            rsx.get("/v1/agent/a_1").mock(
                return_value=httpx.Response(
                    404, json={"codes": ["err_not_found"], "message": "no such agent, token leaked here"}
                )
            )
            with credential(secret_token):
                await call_tool(mcp, "slide_get_agent", {"agent_id": "a_1"})

    records = [r for r in caplog.records if r.name == "slide_mcp.api_client"]
    assert len(records) == 1
    assert records[0].levelno == logging.WARNING
    record = json.loads(records[0].message)
    assert record["tool"] == "slide_get_agent"
    assert record["path"] == "/v1/agent/a_1"
    assert record["status_code"] == 404
    assert record["error_code"] == "not_found"
    line = records[0].message
    assert secret_token not in line
    assert "no such agent" not in line  # raw vendor message must never be logged
