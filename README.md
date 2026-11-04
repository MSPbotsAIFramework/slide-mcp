# slide-mcp

MCP server for [Slide](https://slide.tech) BCDR (backup and disaster-recovery) status,
built for the MSPbots Agent platform. It exposes read-only tools over Slide's REST API
so an agent can answer: which clients/sites and agents (protected systems) are onboarded,
whether devices (Slide appliances) and backup schedules are healthy, whether recent backup
runs succeeded, whether snapshots (recovery points) pass integrity verification, and which
alerts are open.

Transport: MCP Streamable HTTP (`POST /mcp`) + a local `GET /health` probe.
Stack: Python 3.12, [FastMCP](https://github.com/modelcontextprotocol/python-sdk), httpx, uvicorn.
License: Apache-2.0.

---

<div align="center">

## MSPbots Connector

**The MCP Gateway built for MSPs: visible, controlled, and your data stays where it belongs.**

[**Get started at connect.mspbots.ai →**](https://connect.mspbots.ai)

</div>

---

MSPbots Connector gives your AI clients one MCP URL to reach your entire MSP stack (RMM, PSA, documentation, security, finance), and gives you control over who can call which tool and a record of everything that was called.

**Hosted service: [connect.mspbots.ai](https://connect.mspbots.ai)** · Free to use.

### Why Connector

![MSPbots Connector](https://stgoss.mspbots.ai/files/mcp/mspbots-mcp.png)

| | |
|---|---|
| **Visible** | Every tool call is logged: who, which vendor, when. Usage dashboard, CSV export, SIEM streaming. |
| **Controlled** | Role-based, per-tool allowlist. Deny by default. |
| **Protected** | Credentials encrypted per record. AI clients never see your vendor passwords or tokens. |
| **MSP-native** | Built for the MSP stack only: RMM, PSA, documentation, security, finance. |

### Quick start

1. **Sign up** at [connect.mspbots.ai](https://connect.mspbots.ai).
2. **Connect your vendors.** Pick from 150+ connectors and authorize each one on the vendor's own page, or bring your own API keys. No extra vendor accounts needed.
3. **Set access.** Create roles and decide which tools each role may call. Nothing is allowed until you allow it.
4. **Add your MCP URL to your AI client.** Copy the URL from your Connector dashboard into Claude, ChatGPT, Cursor, VS Code, Gemini, Codex, or any MCP-capable client.
5. **Ask your AI to do real work**, and watch every call appear in the audit log.

### Features

**Unified gateway**
- One MCP URL for all your AI clients
- 150+ connectors across the MSP stack
- Custom MCP servers supported, free
- Authorization happens on each vendor's own page; the AI never sees passwords or tokens
- Bring your own credentials: use the vendor API keys you already have
- Multiple accounts per app; connect once, reuse across AI clients
- Tool search: finds the right action for the task
- One sign-in; vendor credentials are injected behind the scenes and OAuth tokens refresh automatically

**Visibility**
- Audit log for every tool call (who, which vendor, when)
- Usage dashboard: call volume, top vendors, error rate, per-user activity
- Export audit logs to CSV, or stream to Loki, Graylog, or LogScale (SIEM)
- Optional recording of tool arguments and result summaries (off by default, enabled per organization)

**Control**
- Per-role, per-tool allowlist, deny by default
- owner / admin / member roles
- SCIM provisioning with Entra ID, Okta, JumpCloud, and Google Workspace

**Security**
- Credentials encrypted one record at a time (AES-256-GCM, per-record key)
- AI clients authenticate with OAuth 2.1 + PKCE
- Vendor responses are scanned for prompt-injection patterns and returned as structured data. This is one layer of defense, not a guarantee against every attack.
- Static egress IP for customer firewall and API allowlisting

### Pricing

**Free.**

Links: [connect.mspbots.ai](https://connect.mspbots.ai) · [mspbots.ai](https://mspbots.ai)

---

## Authentication headers

| Header | Required | Meaning | Where to get it |
|---|---|---|---|
| `X-Slide-Api-Key` | Yes | Slide API key, forwarded to Slide as `Authorization: Bearer <token>` | Slide admin console → Settings → API Keys (see [docs.slide.tech/api](https://docs.slide.tech/api/)) |

Missing the header returns HTTP 401 with a structured body naming the header. The key is
read only from this request header — never from an environment variable, config file, or
any other fallback.

## Tools

Read-only, 12 tools across 7 resource groups:

| Tool | What it does |
|---|---|
| `slide_list_clients` | List the MSP's end-customers/sites onboarded in Slide |
| `slide_list_agents` | List protected systems (agents), optionally scoped to one client |
| `slide_get_agent` | Get one agent's detail, including backup-schedule state |
| `slide_list_devices` | List Slide appliances (devices), optionally scoped to one client |
| `slide_get_device` | Get one device's health: service status, last-seen, storage used/total |
| `slide_list_backups` | List backup runs, optionally scoped to an agent/device/snapshot |
| `slide_get_backup` | Get one backup run's status and error detail if it failed |
| `slide_list_snapshots` | List recovery points (snapshots), optionally scoped to one agent |
| `slide_get_snapshot` | Get one snapshot's integrity verification results (boot/filesystem/service) |
| `slide_list_alerts` | List alerts — unresolved by default, or resolved ones on request |
| `slide_get_alert` | Get one alert by id |
| `slide_list_audit_logs` | List audit log entries (activity trail) |

There are no write or destructive tools in this version: the ticket this connector was
built for asks to *review* BCDR status, not manage Slide infrastructure (pairing agents,
network/VLAN/IPsec configuration, starting restores, billing). See
`docs/tickets/PRD-21274.md` → "Decisions made by DEV01" for the full rationale and how to
extend this later.

## Running locally

```bash
uv sync
uv run python -m slide_mcp
# or, without uv:
python3.12 -m venv .venv && . .venv/bin/activate
pip install -e . --group dev
python -m slide_mcp
```

Listens on `0.0.0.0:8080` by default (override with `MCP_HTTP_HOST` / `MCP_HTTP_PORT`).

```bash
curl -s http://localhost:8080/health
curl -s -X POST http://localhost:8080/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H 'X-Slide-Api-Key: <your Slide API key>' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

## Tests

```bash
uv run pytest
```

Unit tests mock the Slide API (`respx`) — no live Slide account required. A handful of
test cases in `docs/tickets/PRD-21274.ac.json` are marked `manual` / "needs a real Slide
tenant" and are not part of the automated suite.
