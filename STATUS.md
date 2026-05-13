# BurnRate — Status

## Snapshot (2026-05-13)

Phase 1 scaffolding built (kickoff 2026-05-06). No live data ingested yet.
Phase 2 (API proxy): stub only.
6-phase productization roadmap sketched in competitive analysis session (2026-05-12).
See SESSION_LOG.md for the full competitive analysis context.

## The three-step plan (detail)

**Step 1 — Measure**
Cowork estimator reads `mcp__session_info__read_transcript`, estimates per-turn input/output tokens
(with tool-call calibration), writes to `db/burnrate.db` (SQLite). Tags each turn by project.
Renders to `dashboard/dashboard.html`. Calibration: Wilco pastes Anthropic console daily totals
into `docs/calibration.md`; script back-solves tool-type multipliers to within ±20%.

**Step 2 — Mitigate**
After calibration yields stable estimates, write `docs/findings.md` per project:
- Sessions with worst context re-send ratios
- Tools with highest estimated output cost
- Recommended fixes: trim CLAUDE.md, summarize tool outputs, cap history, cache stable prefixes,
  route narrow tasks to Haiku

**Step 3 — Productize**
Phase 2 API proxy between Anthropic/OpenAI SDKs and project code. Logs exact counts including
`cache_read_input_tokens`, `cache_creation_input_tokens`, cost per call. Becomes the precision
data layer and the sellable artifact. Pricing model TBD; leading thesis: OSS proxy + paid
dashboard. See `docs/productization_thesis.md` (to be written after findings).

## Hard constraints — Phase 1 (full detail)

- **No raw session-log access.** Cowork explicitly blocks `request_cowork_directory` against its
  session storage. Cannot read JSONL transcripts directly.
- **`mcp__session_info__read_transcript` returns summarized text only.** User messages, assistant
  messages, and tool-call markers like `(called Read)` — but **not** tool inputs or outputs.
  That's where the biggest tokens hide (file contents, MCP responses, search results).
- **Therefore: estimation, not measurement.**
  - Visible text: counted exactly (chars → tokens at ~3.5 chars/token for mixed text+code; calibratable).
  - Tool I/O: estimated by tool-type with a multiplier table (`Read`, `Bash`, `mcp__*`, etc.).
    Initial defaults are educated guesses.
  - **Calibration loop:** Wilco pastes daily Anthropic console totals into `docs/calibration.md`.
    Script back-solves multipliers so the estimator's daily total matches console within ±20%.
- **Relative comparison is the goal.** Even if absolute numbers are off by 25%, ranking
  sessions / projects / tool types by burn is reliable enough to find the 3–5 biggest fixes.
- **Phase 2 (API proxy) gives precision later.** Exact counts including
  `cache_read_input_tokens`, `cache_creation_input_tokens`, and per-call dollar cost.
  Phase 1 is the personal-use prototype.
