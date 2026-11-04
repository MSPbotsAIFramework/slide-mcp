# PRD-21274 · Code review

## Round 1 · 2026-11-04 · reviewed dev/PRD-21274 @ 8790093 (base main @ 415bfed)

Verdict: changes requested

### Findings

1. [must-fix] src/slide_mcp/server.py, src/slide_mcp/api_client.py, src/slide_mcp/errors.py (whole `src/` tree) — no logging is implemented anywhere (`grep -rn "logging\|logger\|log\." src/` returns no matches). The tech design's own "Non-functional > Observability" section (`docs/tickets/PRD-21274.md`) commits to "structured log per tool call — tool name, resource id/filter summary (no credential), Slide path + status code, duration, error code if any (SOP §6)", and the vendor-mcp-development SOP's §14 checklist lists this under "日志与敏感信息（§6、§11）" — a plain checklist item, not the advisory-marked "面向 Agent 设计（§2，应当）" section, so it is a must item like the credential/error/container groups the same checklist lists alongside it. The Self-test section's own "§14 Checklist" paragraph explicitly claims full coverage of four categories ("Integration contract" §1/§3, "Errors & networking" §4/§5, "Container & deliverables" §0.3/§8, "Agent-facing design" §2) but never mentions the logging/sensitive-info category at all, so the gap was not even flagged as a known limitation to the reviewer. Concretely: `api_client.py`'s `_request` swallows the HTTP status code, retry count and elapsed time on every call and `server.py`'s tool handlers never record which tool ran for which resource id — so a failed or slow `tools/call` against a live Slide tenant in production leaves no trace of which tool, which Slide path, what status code, or how long it took, which is the exact diagnosability this design doc says it provides. Fix: add a structured (JSON or key=value) log line per tool call / per outbound Slide request carrying at least the tool name, the Slide path, the resulting status code, duration, and the mapped error `code` (never the credential or raw vendor `message`/`details`), per SOP §6.

### Fixes

(filled in by the dev leg during rework)
