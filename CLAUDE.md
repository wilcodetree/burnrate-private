# BurnRate — Token-Burn Observability for Agentic LLM Workflows

> **Read this first.** Entry point for any Claude chat about BurnRate.
> Sibling files: STATUS.md (detailed plan + hard constraints), SESSION_LOG.md (history).
> Hub: `../ZeroNonsense.dev/` — BurnRate is the 5th ZeroNonsense.dev project.

## What this is

BurnRate is a token-burn observability tool for agentic LLM workflows. Two layers:

1. **Cowork estimator** (Phase 1, active). Reads Claude Cowork session transcripts via
   `mcp__session_info`, estimates per-turn input/output tokens (with tool-call calibration),
   writes to SQLite, renders a dashboard. Personal use: stop hitting Wilco's usage limits.
2. **API proxy / SDK wrapper** (Phase 2, stub). Sits between projects and Anthropic/OpenAI SDKs.
   Logs every call with exact token counts and project tag. Becomes the precision data layer and,
   eventually, the sellable artifact.

Goal #1 (learn by doing): find the 90% of token waste in Wilco's own workflows and fix it.
Goal #3 (consultancy / talks): once findings exist, the *opinionated insights* are the product.

## Why now

Wilco hits Claude usage limits regularly across hub + CIPHER + JARVIS + DSI + GitHub Actions chats.
CoPilot analysis (kickoff chat 2026-05-06) confirms dominant cost in long agent sessions is
*re-sent context* — often 90%+ of total token spend by turn 30. Without measurement we're guessing.

## The three-step plan

1. **Measure.** Cowork estimator → SQLite → dashboard. Tag by project.
2. **Mitigate.** Write opinionated `findings.md` per project. Trim CLAUDE.md, summarize tool outputs,
   cap history, cache stable prefixes, route narrow tasks to Haiku.
3. **Productize.** Phase 2 API proxy + insights engine. Pricing TBD after findings.

Full plan detail and calibration model: STATUS.md.

## Folder map

```
BurnRate/
├── CLAUDE.md, STATUS.md, SESSION_LOG.md, README.md
├── docs/       ← mission.md, methodology.md, calibration.md, findings.md (post-run)
├── src/        ← projects.py, token_calc.py, cowork_estimator.py, ingest_helper.md,
│                  api_proxy/ (Phase 2 stub)
├── db/         ← schema.sql, burnrate.db (gitignored), raw_transcripts/ (gitignored)
├── dashboard/  ← dashboard.html
└── requirements.txt, .gitignore
```

## Hard constraints (Phase 1 — summary)

Cowork blocks direct JSONL transcript access; `mcp__session_info__read_transcript` returns
summarized text and tool-call markers only — tool I/O is estimated by type, not measured.
Calibration loop adjusts multipliers against Anthropic console totals to within ±20%.
Full constraint detail: STATUS.md.

## How to brief a new BurnRate chat

1. Read this CLAUDE.md.
2. Check SESSION_LOG.md for what's changed recently.
3. Open STATUS.md for the full three-step plan and Phase 1 hard constraints.
4. Read docs/methodology.md before touching estimation code.
5. If running an ingest pass: see src/ingest_helper.md.
6. End of session: append one paragraph to SESSION_LOG.md.

## Things Claude should never assume

- **BurnRate is not yet a product.** Personal tool through ~v0.3 minimum. No multi-tenancy, auth,
  or pricing pages until findings prove it's worth selling.
- **Phase 1 numbers are estimates, not ground truth.** Always state calibration date and
  accuracy band when reporting figures.
- **"Token burn" ≠ "dollar cost."** Cowork uses Wilco's subscription (usage-limited, not metered
  in dollars to Wilco). Per-call dollar figures only meaningful in Phase 2.
- **Memory facts may be stale.** Verify file paths and function names before acting.

---

*Created: 2026-05-06 (kickoff session in hub).*
