# PRD-21274 · Code review

Status: frozen @ 69b9ef6

## Round 1 · 2026-11-04 · reviewed dev/PRD-21274 @ 8790093 (base main @ 415bfed)

Verdict: changes requested

### Findings

1. [must-fix] src/slide_mcp/server.py, src/slide_mcp/api_client.py, src/slide_mcp/errors.py (whole `src/` tree) — no logging is implemented anywhere (`grep -rn "logging\|logger\|log\." src/` returns no matches). The tech design's own "Non-functional > Observability" section (`docs/tickets/PRD-21274.md`) commits to "structured log per tool call — tool name, resource id/filter summary (no credential), Slide path + status code, duration, error code if any (SOP §6)", and the vendor-mcp-development SOP's §14 checklist lists this under "日志与敏感信息（§6、§11）" — a plain checklist item, not the advisory-marked "面向 Agent 设计（§2，应当）" section, so it is a must item like the credential/error/container groups the same checklist lists alongside it. The Self-test section's own "§14 Checklist" paragraph explicitly claims full coverage of four categories ("Integration contract" §1/§3, "Errors & networking" §4/§5, "Container & deliverables" §0.3/§8, "Agent-facing design" §2) but never mentions the logging/sensitive-info category at all, so the gap was not even flagged as a known limitation to the reviewer. Concretely: `api_client.py`'s `_request` swallows the HTTP status code, retry count and elapsed time on every call and `server.py`'s tool handlers never record which tool ran for which resource id — so a failed or slow `tools/call` against a live Slide tenant in production leaves no trace of which tool, which Slide path, what status code, or how long it took, which is the exact diagnosability this design doc says it provides. Fix: add a structured (JSON or key=value) log line per tool call / per outbound Slide request carrying at least the tool name, the Slide path, the resulting status code, duration, and the mapped error `code` (never the credential or raw vendor `message`/`details`), per SOP §6.

### Fixes

1. [must-fix, finding 1] Added structured per-call logging, commit `53feae8`:
   - `src/slide_mcp/api_client.py`: `SlideClient._request` is the single choke point every one of the 12 tool-backing methods funnels through, so it now emits exactly one JSON log line per outbound Slide request, carrying `tool` (e.g. `slide_list_clients`, threaded in explicitly from each of the 12 call sites — the method name already maps 1:1 to the MCP tool name), `method`, `path` (already carries the resource id for `get_*` calls, e.g. `/v1/agent/a_1`), `params` (the filter/id summary for `list_*` calls — never the credential, which lives only in the client's `Authorization` header and is never passed into `_request`), `status_code`, `attempts`, `duration_ms` (measured from before the retry loop, so it covers the full tool-call latency including retries), and `error_code`. Logged at INFO on success, WARNING on failure (unreachable upstream counts as a failure, `status_code: 0`, `error_code: "upstream_error"`).
   - `src/slide_mcp/error_codes.py` (new): extracted the HTTP-status → error-code mapping that used to live only in `errors.py` (`ERROR_CODE_BY_STATUS`) into its own module, so the new log line's `error_code` and the client-facing envelope's `code` (`errors.from_slide_error`) are guaranteed to agree — one mapping, not two copies that could drift. `errors.py` now imports `map_status_to_code` from it instead of keeping its own copy.
   - `src/slide_mcp/__main__.py`: added `logging.basicConfig(level=logging.INFO, format="%(message)s")` before `uvicorn.run(...)` — without it the new log lines would never reach stdout, since uvicorn's `log_level="info"` only configures uvicorn's own loggers, not a plain `logging.getLogger(...)` the app code creates.
   - Never logs the raw vendor `message`/`details` — only our own mapped `error_code`; verified by `tests/test_logging.py::test_failed_call_logs_mapped_error_code_never_the_credential`, which plants a vendor message containing a secret token string and the literal text "no such agent", and asserts neither appears anywhere in the log line.
2. Self-test's "§14 Checklist" paragraph in `docs/tickets/PRD-21274.md` is unchanged (that doc is frozen, see S1 "评审返工" — only this review doc's Fixes section is touched for a review-rework round); the logging/sensitive-info category it was missing is now covered and verified below.
3. Gates re-run on the branch after this fix, no base-branch sync needed (`origin/main` is still `415bfed`, unchanged since this branch was cut):
   - `uv run pytest`: **16 passed** (14 baseline + 2 new logging tests: `test_successful_call_logs_tool_path_status_and_duration`, `test_failed_call_logs_mapped_error_code_never_the_credential`). 0 regressions against the baseline 14.
   - Smoke test (local `uvicorn` boot): `GET /health` → 200 `{"status":"ok"}`; `POST /mcp` with no `X-Slide-Api-Key` → 401 `{"error":{"code":"unauthorized",...}}` (unchanged behavior).
   - `tools/list` via `mcp.list_tools()`: still 12 tools, names unchanged (`test_tools_list_snapshot` passes).
   - Chinese-character scan (`grep -rnP '[\x{4e00}-\x{9fff}]' --exclude-dir=.git --exclude-dir=.venv .`): only hit is the Chinese SOP-section-name quote already inside this frozen review doc's Round 1 finding text (not `src/`, not introduced by this fix) — left untouched since the Findings section is the reviewer's record, not mine to edit.
   - `gitleaks`: not installed on this machine (same as the original Self-test); fell back to the same `git log -p | grep -Ei '(token|secret|api[_-]?key|password|bearer)\s*[=:]'` scan — no real credential found, only variable names and the pre-existing `sk_super_secret_value` test fixture (now also reused, unmodified in spirit, by the new negative-leak assertion in `test_logging.py`).
   - README Connector section and `.gitignore`/`.dockerignore`: untouched by this fix, no re-check needed.

## Round 2 · 2026-11-04 · reviewed dev/PRD-21274 @ 69b9ef6 (base main @ 415bfed)

Verdict: approved

### Round 1 fix verification

Round 1's only must-fix (finding 1, no structured logging) is resolved. Verified independently, not taken on the Fixes section's word:

- `src/slide_mcp/api_client.py:88-96` — `_request` now takes `tool` as a required keyword-only argument and calls `_log_call` (`api_client.py:26-61`) on every exit path: the retry-exhausted/unreachable branch (`status_code=0, error_code="upstream_error"`), the `< 400` success branch (`error_code=None`, INFO), and the `>= 400` error branch (`error_code=map_status_to_code(...)`, WARNING). All three paths through the request loop are covered, not just the happy path.
- All 12 call sites into `_request` (one per tool-backing method, `api_client.py:166-249`) now pass an explicit `tool=` string that matches the corresponding MCP tool name 1:1 (`grep -c '_request(' src/slide_mcp/api_client.py` → 13 matches: 1 definition + 12 call sites, matching the 12-tool count). No call site was missed.
- Credential safety: `SlideClient.__init__` (`api_client.py:78-83`) puts the bearer token straight into `httpx.AsyncClient(headers=...)`; the token is never a parameter of `_request` or `_log_call`, so there is no code path by which it could reach the log line. `params` only ever carries list filters / ids built by the tool layer (`limit`, `offset`, `client_id`, etc.). Confirmed by running `tests/test_logging.py::test_failed_call_logs_mapped_error_code_never_the_credential` myself (not just reading it): it plants a secret token and the raw vendor message `"no such agent"` in the mocked 404 body and asserts neither string appears in the log record — passes.
- `src/slide_mcp/error_codes.py` (new) is the only place `_ERROR_CODE_BY_STATUS` is defined; `errors.py` now imports `map_status_to_code` from it (`grep -rn "ERROR_CODE_BY_STATUS" --include=*.py .` → zero hits outside `error_codes.py`, so there is no second copy left to drift from the log line's mapping). `errors.from_slide_error` and `_log_call`'s `error_code` are guaranteed to agree for the same status.
- `src/slide_mcp/__main__.py:16` adds `logging.basicConfig(level=logging.INFO, format="%(message)s")` before `uvicorn.run(...)` — without this the plain `logging.getLogger("slide_mcp.api_client")` calls would be dropped (uvicorn's `log_level="info"` only configures uvicorn's own loggers). Placement (before `uvicorn.run`, which blocks) is correct.

No residual gap: the fix covers success, HTTP error, and unreachable-upstream paths, for every tool, without logging the credential or the raw vendor message.

### New diff since Round 1 (`8e2524f...69b9ef6`)

Reviewed the full diff (`api_client.py`, new `error_codes.py`, `errors.py`, `__main__.py`, new `tests/test_logging.py`, plus this review doc's own Fixes section). No new must-fix:

- The refactor that extracts `error_codes.py` is a pure move (no behavior change) — `errors.from_slide_error` produces the same codes as before (`400/422→invalid_argument`, `401/403→unauthorized`, `404→not_found`, `429→rate_limited`, `0`/`>=500`/anything else→`upstream_error`), confirmed by reading both the old and new mapping side by side.
- `tests/test_logging.py`'s two new tests exercise the success path and the failure path independently, assert on the parsed JSON structure (not just "a log line exists"), and the negative-leak assertion checks both the secret token and the raw vendor message string — this is the kind of test that would actually catch a regression, not a test that only proves itself passes.
- Full gate re-run on this reviewer's machine (not only the dev leg's report): `uv run pytest -q` → **16 passed**, 0 failed, matching the `[DEV]` stub's claim exactly. Chinese-character scan clean outside the pre-existing quoted SOP-section-name inside this review doc's own frozen Round 1 finding text (not `src/`, not a new introduction). README Connector section (`README.md:16-86`) is byte-for-byte identical to `~/.claude/skills/vendor-mcp-development/reference/readme-connector-section.md` (`diff` exit 0) — unchanged since Round 1, where it was also found compliant.
- `origin/main` is still `415bfed` (unchanged since the branch was cut), so no base-sync was needed before this round either, and none is needed before merging.

### Suggestions

None beyond what Round 1 already covered.

### Conclusion

Both rounds considered, the connector meets the MCP review bar (`legs/review.md` R3, `references/mcp-track.md` §4.3): credentials are request-scoped and never logged; tool names/params/errors are structured and consistent; tests cover the fix; README Connector section matches the template; no Chinese outside the frozen reviewer note. Proceeding to merge into `main`, INT registration (first-ever for this vendor, `mcppub register`), and the connector wiki.
