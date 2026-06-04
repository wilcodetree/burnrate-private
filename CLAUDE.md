# BurnRate — Token-Burn Observability for Agentic LLM Workflows

> **Read this first.** Entry point for any Claude chat about BurnRate.
> Sibling files: STATUS.md (detailed plan), SESSION_LOG.md (history).
> Hub: `../ZeroNonsense.dev/` — BurnRate is the 5th ZeroNonsense.dev project.

## What this is

BurnRate is a token-burn observability tool for agentic LLM workflows. Two layers:

1. **Cowork estimator** (Phase 1, active). Reads JSONL session files written by Claude Code /
   Cowork into `~/.claude/projects/` directly. Extracts **exact** per-turn token counts from the
   Anthropic API usage fields embedded in each assistant message — no estimation, no calibration.
   Writes to JSON store, renders a dashboard. Personal use: stop hitting Wilco's usage limits.
2. **API proxy / SDK wrapper** (Phase 2, stub). Sits between projects and Anthropic/OpenAI SDKs.
   Logs every call with exact token counts and project tag. Becomes the precision data layer and,
   eventually, the sellable artifact.

Goal #1 (learn by doing): find token waste in Wilco's own workflows and fix it.
Goal #3 (consultancy / talks): once findings exist, the *opinionated insights* are the product.

## Key finding (measured, not estimated)

Cache reads are **95–98% of effective input** across all measured sessions — not the 90% hypothesis.
Fresh input per turn: 1–3 tokens. Cache read per turn grows from ~23K at turn 1 to ~127K by turn 186.
Full findings: `docs/findings.md`.

## The three-step plan

1. **Measure.** JSONL ingester → JSON store → dashboard. Tag by project. ✅ Done.
2. **Mitigate.** Write opinionated `findings.md`. Trim CLAUDE.md files, use /compact at turn 25–30.
3. **Productize.** Phase 2 API proxy + insights engine. Deferred until findings prove value.

## Data source (Phase 1)

Cowork sessions write JSONL to `~/.claude/projects/C--Users-WilcoDeTree-OneDrive---Valona-Intelligence-Claude-Cowork-Output/*.jsonl`.
Each assistant message embeds exact `input_tokens`, `cache_creation_input_tokens`,
`cache_read_input_tokens`, `output_tokens`. BurnRate reads these directly. Source folder is
configurable via `config.json`. Weekly limit and reset schedule also in `config.json`.
Automatic ingestion: daily 08:00 via Cowork scheduled task + `run_ingest.bat` for Task Scheduler.
**30-day deletion window** is the main operational risk — ingest daily.

## Folder map

```
BurnRate/
├── CLAUDE.md, STATUS.md, SESSION_LOG.md, README.md, config.json
├── docs/       ← findings.md (real data), mission.md, methodology.md, calibration.md
├── src/        ← cowork_estimator.py (v2, JSONL), projects.py, token_calc.py (legacy)
│                  api_proxy/ (Phase 2 stub)
├── db/         ← sessions.json, turns.json, daily_totals.json, ingest_state.json
│                  forecast.json, meta.json, ingest_log.txt, api_usage/*.csv
├── dashboard/  ← dashboard.html (dark TokenFinOps-style, 7 sections)
├── run_ingest.bat  ← Windows Task Scheduler runner (ingest + rollup + forecast)
└── requirements.txt, .gitignore
```

## How to brief a new BurnRate chat

1. Read this CLAUDE.md.
2. Check SESSION_LOG.md for what changed recently.
3. Read `docs/findings.md` for current measurement results and mitigations.
4. Open STATUS.md for architecture detail.
5. End of session: append one paragraph to SESSION_LOG.md.

## Things Claude should never assume

- **BurnRate is not yet a product.** Personal tool through ~v0.3 minimum. No multi-tenancy, auth,
  or pricing pages until findings prove it's worth selling.
- **Phase 1 numbers are exact, not estimates.** From Anthropic API `usage` fields in the JSONL.
  No calibration factors apply.
- **"Token burn" ≠ "dollar cost."** Cowork is subscription-limited, not metered. Per-call dollar
  figures only meaningful in Phase 2.
- **FUSE mount corrupts files on edit.** Always write large files via bash heredoc to /tmp, then
  cp to mount. Never use Edit tool for files >100 lines on the mount.
- **Memory facts may be stale.** Verify file paths and function names before acting.

---

*Last updated: 2026-05-19 (full rebuild — JSONL ingester v2, dark dashboard, findings, forecast).*

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
