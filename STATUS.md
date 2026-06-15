# BurnRate — Status

## Snapshot (2026-06-15)

Phase 1 fully operational. JSONL ingester v2 running daily via `run_ingest.bat`. Exact token counts
from Anthropic API `usage` fields — no estimation. Dashboard live. Calibration producing clean
weekly limit estimates (snapshot-pair method). Phase 2 (API proxy): stub only, deferred.

---

## Architecture (Phase 1 — current)

**Data flow:**
```
Cowork sessions (Store app)
  → %LOCALAPPDATA%\Packages\Claude_*\LocalCache\Roaming\Claude\local-agent-mode-sessions\
  → bat step 1b mirrors *.jsonl to BurnRate\_jsonl_mirror\

Claude Code CLI sessions
  → %USERPROFILE%\.claude\projects\C--...-Cowork-Output*\*.jsonl
  → bat step 1a mirrors to BurnRate\_jsonl_mirror\

_jsonl_mirror\ → ingest (cowork_estimator.py)
  → %LOCALAPPDATA%\BurnRate\db\  (local write, no OneDrive FUSE race)
  → sync_to_onedrive.py copies back → BurnRate\db\  (OneDrive, for sandbox reads)

Sandbox (claude.ai Cowork) reads from BurnRate\db\ (OneDrive)
Sandbox writes ONLY claude_ai_tracking.json (snapshot command)
```

**Key files:**
- `src/cowork_estimator.py` — JSONL ingester v2; commands: ingest, rollup, forecast, render, snapshot, report
- `src/projects.py` — project auto-tagger (regex patterns per project)
- `src/sync_to_onedrive.py` — post-ingest sync, handles paths with spaces
- `db/sessions.json` — canonical session store (written to local AppData only by ingest)
- `db/claude_ai_tracking.json` — calibration snapshot history (written by sandbox `snapshot` command)
- `db/project_overrides.json` — manual project retags (survive re-ingest, keyed by session_id)
- `db/ingest_state.json` — JSONL file mtimes (dedup guard)
- `dashboard/dashboard.html` — dark TokenFinOps-style; 7 sections; Chart.js
- `run_ingest.bat` — Windows Task Scheduler runner (daily 08:00); v4b

---

## Calibration state

**Method:** delta-pair. Take Snapshot A (low weekly %, start of week), Snapshot B (10%+ higher later).
`implied_limit = delta_cowork / delta_pct × 100`. Config `weekly_token_limit` auto-updates to blended value.

**Known unit mismatch:** BurnRate's `total_effective_input` is dominated by cache reads (95–98%).
Cache reads accumulate fast but Anthropic's usage meter weights them cheaply. Delta-pair calibration
is more reliable than point estimates but still noisy. True fix: switch to `input_tokens +
cache_creation_tokens + output_tokens` (fresh compute only). Deferred to post-Jul-5 re-calibration.

**Doubled credits:** Anthropic is running 2× Cowork usage promo until **July 5, 2026**. All
calibration snapshots before Jul 5 are inflated 2×. Estimated real permanent limit: ~125M tokens/week.

**Hub sessions use Fable model** (~2× token burn vs Sonnet). Hub token counts in BurnRate are
disproportionately high.

**Snapshot history (valid):**

| # | Date | Weekly % | TWC tokens | Implied limit | Notes |
|---|------|----------|-----------|---------------|-------|
| A | Jun 10 | 18% | 325,019,343 | — | Baseline, no prior snap |
| B | Jun 12 | 38% | 375,049,123 | 250,148,900 | First clean calibration |
| C | Jun 12 eve | 56% | 443,537,234 | 380,489,505 | Config → 324,617,958 (blended) |
| A | **Jun 15** | **17%** | **139,818,011** | **—** | **New week baseline; Snapshot B pending** |

**Current config:** `weekly_token_limit = 324,617,958` (blended; doubled-credits period).
**Re-calibrate week of Jul 7** for permanent baseline.

---

## Project tagging

Auto-tagger in `src/projects.py` uses regex patterns per project. Patterns added Jun 12:
- `jarvis`: `\bJARVIS\b`, `langgraph`, `local agent`, `voice agent`, `consulting work`, `time registration`, `time.entry`
- `hub`: `ZeroNonsense\.dev`, `\bZND\b`, `\bhub\b`, `company brief`, `portfolio\.md`, `DEADLINES\.md`, `roadmap\.md`, `next_steps`, `SESSION_LOG`

Manual overrides: `db/project_overrides.json` (session_id → project). Applied after auto-tagger
during ingest; survive re-ingest. Currently overrides 2 sessions (Jun 12 diagnosis).

---

## Pending

| Item | Priority | Notes |
|------|----------|-------|
| Take Snapshot B (week of Jun 15) | High | When weekly % hits ~27%+ (10pt delta over 17% baseline) |
| Re-calibrate week of Jul 7 | High | First post-double-credits week; expect ~125M real limit |
| Switch calibration to fresh-compute metric | Medium | Use `input_tokens + cache_creation_tokens + output_tokens` instead of `total_effective_input` |
| Add session-level project override UI to dashboard | Low | Currently done manually via JSON |

---

## FUSE mount rules (do not break)

- **Never use Edit tool on db/ or src/ files.** OneDrive FUSE mount truncates large JSON on write.
- **Always write via bash:** `cat > /tmp/file.json << 'EOF'` ... `EOF`, then `cp /tmp/file.json /mnt/path/`.
- **Sandbox writes only:** `claude_ai_tracking.json` (snapshot command only).
- **Sandbox never runs:** `ingest` or writes `sessions.json` / `ingest_state.json`.

---

*Last updated: 2026-06-15.*
