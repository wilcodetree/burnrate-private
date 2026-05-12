# BurnRate — Token-Burn Observability for Agentic LLM Workflows

> **Read this first.** Entry point for any Claude chat about BurnRate.
> The hub (`../ZeroNonsense.dev/`) tracks BurnRate as the 5th ZeroNonsense.dev project.
> Project-internal architecture and conventions live here. Cross-project
> portfolio context lives in the hub.

## What this is

BurnRate is a token-burn observability tool for agentic LLM workflows.
Two layers:

1. **Cowork estimator** (Phase 1, active). Reads Claude Cowork session
   transcripts via `mcp__session_info`, estimates per-turn input/output
   tokens (with tool-call calibration), writes to SQLite, renders a
   dashboard. Personal use: stop hitting Wilco's daily/weekly Claude usage
   limits.
2. **API proxy / SDK wrapper** (Phase 2, stub). Sits between projects
   (CIPHER n8n, JARVIS, future DSI/GitHub Actions) and Anthropic/OpenAI
   SDKs. Logs every call with exact token counts (input, output, cache
   reads, cache writes) and project tag. Becomes the precision data layer
   and, eventually, the sellable artifact.

Goal #1 (learn by doing): we'll find the 90% of token waste in Wilco's own
workflows and fix it before claiming it's worth selling.
Goal #3 (consultancy / talks): once we have findings, the *opinionated
insights* engine — not the raw observability — is the product.

## Why now

Wilco hits Claude usage limits regularly across hub + CIPHER + JARVIS +
DSI + GitHub Actions chats. The CoPilot analysis (pasted into the kickoff
chat 2026-05-06) confirms the dominant cost in long agent sessions is
*re-sent context*, not new work — often 90%+ of total token spend by turn
30. Without measurement we're guessing which sessions / tools / projects
are the worst offenders. With measurement we can be precise about where
to apply prompt caching, history truncation, RAG, and session sharding.

## The three-step plan

1. **Measure.** Cowork estimator → SQLite → dashboard. Tag by project.
2. **Mitigate.** Once data is in, write opinionated `findings.md` per
   project. Concrete fixes: trim CLAUDE.md, summarize tool outputs, cap
   history, cache stable prefixes, route narrow tasks to Haiku.
3. **Productize.** Phase 2 API proxy + insights engine. Pricing model
   TBD; OSS proxy + paid dashboard is the leading thesis. See
   `docs/productization_thesis.md` (to be written after we have findings).

## Folder map

```
BurnRate/
├── CLAUDE.md                       ← you are here
├── README.md                       ← short public-facing description
├── SESSION_LOG.md                  ← what each chat changed (most-recent on top)
│
├── docs/
│   ├── mission.md                  ← why this exists, brand voice, scope
│   ├── methodology.md              ← how we estimate tokens (chars/tool-calls/calibration)
│   ├── calibration.md              ← capture Anthropic console totals; back-solve multipliers
│   └── findings.md                 ← (filled after first run) per-project waste analysis
│
├── src/
│   ├── projects.py                 ← session→ZND project tagger
│   ├── token_calc.py               ← char→token + tool-call multiplier model
│   ├── cowork_estimator.py         ← parse transcripts → SQLite (Phase 1 main)
│   ├── ingest_helper.md            ← how Claude (this chat) feeds raw transcripts in
│   └── api_proxy/                  ← Phase 2 stub
│       └── README.md
│
├── db/
│   ├── schema.sql                  ← SQLite schema (sessions, turns, calibration, projects)
│   ├── burnrate.db                 ← runtime; gitignored
│   └── raw_transcripts/            ← per-session JSON dumps fed by Claude; gitignored
│
├── dashboard/
│   └── dashboard.html              ← Cowork artifact, reads SQLite via small bridge
│
├── requirements.txt
└── .gitignore
```

## Hard constraints (Phase 1 — Cowork estimator)

- **No raw session-log access.** Cowork explicitly blocks
  `request_cowork_directory` against its session storage. We cannot read
  JSONL transcripts directly. We must use `mcp__session_info__read_transcript`
  which returns *summarized* text: user messages, assistant messages, and
  tool-call markers like `(called Read)` — but **not** tool inputs or
  outputs. That's where the biggest tokens hide (file contents, MCP
  responses, search results).
- **Therefore: estimation, not measurement.** We use a hybrid model:
  - Visible text: counted exactly (chars → tokens at ~3.5 chars/token for
    mixed text+code; calibratable).
  - Tool I/O: estimated by tool-type with a multiplier table (`Read`,
    `Bash`, `mcp__*`, etc.). Initial defaults are educated guesses.
  - **Calibration loop:** Wilco pastes daily Anthropic console totals
    into `docs/calibration.md`. Script back-solves multipliers so the
    estimator's daily total matches console within ±20%.
- **Relative comparison is the goal.** Even if absolute numbers are off
  by 25%, ranking sessions / projects / tool types by burn is reliable
  enough to find the 3-5 biggest fixes.
- **Phase 2 (API proxy) gives precision later.** That's where we get
  exact counts including `cache_read_input_tokens`, `cache_creation_input_tokens`,
  and per-call cost in dollars. Phase 1 is the personal-use prototype.

## How to brief a new BurnRate chat

1. Read this `CLAUDE.md` top-to-bottom.
2. Check `SESSION_LOG.md` for what's changed recently.
3. Read `docs/methodology.md` to understand the estimation model before
   touching code.
4. If running an ingest pass: see `src/ingest_helper.md`.
5. End of session: append a one-paragraph entry to `SESSION_LOG.md`.

## Things Claude should never assume

- **BurnRate is not yet a product.** It's a personal tool through ~v0.3
  at minimum. Don't add multi-tenancy, auth, or pricing pages until
  findings prove it's worth selling.
- **Numbers from Phase 1 are estimates, not ground truth.** Always state
  the calibration date and accuracy band when reporting figures.
- **"Token burn" ≠ "dollar cost" automatically.** Cowork uses Wilco's
  Anthropic subscription (usage-limited, not metered in dollars to
  Wilco). Per-call dollar figures only become meaningful in Phase 2 with
  the API proxy.
- **Memory facts may be stale.** Verify file paths and function names
  against current state before acting.

---

*Created: 2026-05-06 (kickoff session in hub).*
