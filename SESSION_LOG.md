# SESSION_LOG.md — BurnRate

Most-recent on top. One paragraph per session. Append at end of each chat.

---

## 2026-06-12 — First clean calibration; Store app path fully working

**Calibration finally fired cleanly.** Snapshot A (Jun 10, 18%, 325M tokens) + Snapshot B (Jun 12, 38%, 375M tokens) gave delta_pct=20%, delta_cowork=50M → **implied weekly limit ≈ 250M tokens**. Config `weekly_token_limit` auto-updated from 63.8M → 194M (blended conservative). The old 63–83M estimate was wrong — it was based on only 1 of 9 sessions being counted (CLI sessions only, Store app sessions missing). 250M is the first estimate based on complete data. Also: skill `/log-time-from-sessions` Step 3 fixed — hardcoded sandbox name `busy-eager-dirac` replaced with dynamic `SANDBOX=$(ls /sessions/ | grep -v lost | tail -1)`. Dashboard re-rendered: 67 sessions, 40 daily rows.

---

## 2026-06-07 (late night) — Store app JSONL path fix; calibration contaminated by backfill

Identified the root cause of why Cowork desktop sessions were never being ingested. Step 1b of `run_ingest.bat` was pointing at `%APPDATA%\Claude\local-agent-mode-sessions` (the app's internal virtual view) rather than the real Windows Store app path: `%LOCALAPPDATA%\Packages\Claude_*\LocalCache\Roaming\Claude\local-agent-mode-sessions`. The bat was running the PowerShell scan but finding zero files because from outside the app (CMD), the Claude folder doesn't exist under standard `%APPDATA%`. **Fix (bat v4b)**: step 1b now uses `Join-Path $env:LOCALAPPDATA 'Packages\Claude_*\LocalCache\Roaming\Claude\local-agent-mode-sessions'` with a wildcard for the package ID. First successful run captured all previously-missed sessions: sessions.json jumped from 17 to 56 sessions. This week's sessions went from 1 to 9 (228M effective input tokens total at 39% Anthropic weekly usage). **Calibration snapshot #21 is invalid**: the 2% usage delta corresponded to a 245M token delta-cowork, giving an absurd 12.3B implied limit. The delta was polluted by 8 sessions being discovered for the first time (not new consumption). Snapshot marked invalid in `claude_ai_tracking.json`. Point estimate from the new data: 228M/39% ≈ 585M weekly limit, but unit mismatch between BurnRate's `total_effective_input` (cache-read-heavy) and Anthropic's usage metric is unresolved — needs a proper calibration pair taken next week from a clean baseline.

---

## 2026-06-07 (evening) — Race condition resolved, local AppData architecture, sync fixed

Three-part session. (1) **OneDrive/FUSE write-collision race condition (RESOLVED)**: bat now writes all ingest files to `%LOCALAPPDATA%\BurnRate\db` via `--db-dir` override, then copies back to OneDrive using `src/sync_to_onedrive.py` (Python shutil.copy2 — handles paths with spaces reliably). Sandbox never writes sessions.json or ingest_state.json. CLAUDE.md updated. Root cause of the `[\r\n]` sessions.json corruption was a FOR loop `copy` command silently failing on paths containing spaces. (2) **Local AppData folder connected as Cowork mount** (`AppData\Local\BurnRate\db`): gives sandbox direct read access to the real sessions data, bypassing OneDrive FUSE lag entirely. The first fully successful bat run confirmed: `[SYNC] Done — 5/5 files copied to OneDrive` at 22:29 CEST. (3) **Snapshot #19 taken**: weekly=37%, session=70%, this_week_cowork=5,640,096. Calibration did not fire (delta_cowork=0 — current session still live/not ingested). Session should be ingested after close + bat run; a post-1AM-reset calibration pair will give clean data for next week's limit estimate.

---

## 2026-06-07 — Data-loss recovery, bat wildcard fix, JSONL location investigation

Session picked up mid-stream (context limit from Jun 3–4 session). Three items addressed. (1) **sessions.json data-loss (again)**: sessions.json had dropped to 1 session (9a7bee4f, a Jun 6 hub session). Root cause unclear — the data-loss guard in the ingest only protects the n_ok=0/empty case, but the store had somehow been reset before the last bat run. Recovery: reset all 17 ingest_state mtimes to 0, cleared sessions/turns, re-ran ingest — all 17 sessions restored cleanly. (2) **JSONL source location clarified**: BurnRate reads from `~\.claude\projects\C--...-Cowork-Output*\` (wildcard added in previous session), mirrored to `BurnRate\_jsonl_mirror\`. The `~\.claude\session-data\*.tmp` files visible in Explorer are Cowork's own session-state layer (conversation resumption), NOT API usage logs — different format, not readable by the ingest pipeline. (3) **Today's session (Jun 7) still not captured**: current conversation JSONL hasn't been flushed to `~\.claude\projects\` yet. Weekly snapshot shows 21% used but BurnRate sees 0 this-week tokens. Run `.\run_ingest.bat` after this session ends to capture it. Weekly limit estimate at 63.8M (from Jun 4 calibration); expect a fresh calibration pair once today's session ingests.

---

## 2026-06-03 — Snapshot calibration workflow, API import, two bug fixes

Added CIPHER Anthropic API CSV export for Apr–May 2026 (79 daily records, 4 models: Haiku, Sonnet 4.5, Sonnet 4.6, Opus 4.7, 83.8% cache share). Wrote `docs/cipher_api_usage_guide.md` — step-by-step manual for future CSV exports and imports. Fixed two bugs in `cowork_estimator.py`: (1) `_ts_ge()` was called with `week_start.isoformat()` (a string) instead of `week_start` (datetime), causing a silent TypeError that returned False for every snapshot lookup — the calibration never found prior-week snapshots; (2) the calibration anchor picker always used `prev_this_week[-1]` (most-recent), which was often the same % as current giving delta_pct=0 — replaced with a loop that walks backwards to find the first anchor where both delta_pct > 0 and delta_cowork > 0. First calibration successfully fired: implied limit ~83M, blended to 73M in config.json. New week started (reset Sun Jun 1): 22% used = 19.6M Cowork tokens, implying ~89M true weekly limit. Forecast and dashboard re-rendered. True weekly limit will self-correct over next few daily snapshot pairs.

---

## 2026-05-19 — Full dashboard rebuild + forecast engine + findings (TokenFinOps-inspired)

Reviewed TokenFinOps technical doc and UI screenshots (dark theme, cumulative forecast chart, budget gauges, model router). Built a complete BurnRate upgrade across 6 files. (1) `src/projects.py`: fixed hub detection — root Cowork Output cwd now correctly tags sessions as `hub` instead of `other`; added `_clean_title()` to strip `<command-message>` XML tags from session titles. (2) `config.json`: added `weekly_token_limit` (default 50M), `weekly_reset_day` and `weekly_reset_hour` fields. (3) `src/cowork_estimator.py` (v2 continued): added `forecast` command that computes current-week burn vs limit, 7-day moving average, days-to-limit projection, and writes `db/forecast.json`; added `run_ingest.bat` now calls forecast step. (4) `dashboard/dashboard.html`: complete rebuild — 1132-line dark-theme single-page app with 7 sections (Dashboard, Forecast, Projects, Sessions, Cache Analysis, API Actual, Recommendations); uses Chart.js; KPI cards, SVG arc gauge, stacked bar charts, cumulative burn line with dashed forecast, session table with cache bars, cache growth per turn, model pricing reference table, auto-generated recommendations ranked by impact. All files written via bash to /tmp then cp to FUSE mount to avoid truncation corruption. (5) `docs/findings.md`: first real findings written from measured data — cache is 95–98% not 90%, fresh input is 1–3 tokens/turn, session length compounds cost, CIPHER API already well-optimised at 86% cache hit, mitigation priority list with estimated savings. (6) `CLAUDE.md`: rebuilt to 80 lines — removed duplicate folder map, updated with real finding (95–98% cache), added FUSE mount corruption warning, marked step 1 of 3-step plan as done.

---

## 2026-05-18 — JSONL direct ingestion (v2): Phase 1 estimation model retired

Discovered that Cowork sessions write full JSONL to `~/.claude/projects/C--Users-WilcoDeTree-OneDrive---Valona-Intelligence-Claude-Cowork-Output/*.jsonl`, with exact Anthropic API `usage` objects embedded in every assistant message (`input_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`, `output_tokens`). Verified across 5 uploaded sample sessions. Key finding: cache read tokens represent 88–98% of total effective input across all sessions — the original 90% hypothesis was conservative. Rewrote `src/cowork_estimator.py` (v2) to parse JSONL directly instead of using `mcp__session_info` + estimation. New data model: exact token fields per session and turn, `ingest_state.json` tracks file mtimes for incremental runs on active/growing sessions. Created `config.json` for configurable source folder paths (supports multiple folders, easy to change if OneDrive path changes). Created `run_ingest.bat` for Windows Task Scheduler — runs `ingest` + `rollup`, appends timestamped output to `db/ingest_log.txt`, trims log to 500 lines. Updated CLAUDE.md: removed stale "Cowork blocks JSONL access" constraint, replaced with accurate data source description. Token_calc.py and old estimation code kept for reference but no longer called by the main pipeline. Smoke test on 5 sample sessions: 26.3M effective input tokens, 504k output tokens parsed correctly with project tagging and turn-level rows.

---

---

## 2026-05-13 — CLAUDE.md compacted; STATUS.md created

Restructured CLAUDE.md: compacted to 72 lines (from 132); moved full "Hard constraints
(Phase 1)" section and "Three-step plan" detail to new STATUS.md. CLAUDE.md retains
2-sentence hard-constraints summary and 3-bullet plan; full detail pointer to STATUS.md.
"Why now" section trimmed. No guardrail wording changed.

---

## 2026-05-12 - Competitive analysis + phased productisation roadmap

Wilco shared five competitor links (ccburn, AleBles/burnrate,
getburnrate.io, getburnrate.vercel.app, gammaglitch/burnrate) and asked
for a status + plan to make BurnRate a "super tool" and money maker.
Fetched all four sites for landscape. Key finding: `getburnrate.io` is
the real commercial threat (Free/Pro $12/Team $29, 7 providers, 46
optimization rules, polished single Go binary, team dashboard with
privacy-safe aggregation). Every competitor parses local JSONL session
files from `~/.claude/projects/` etc. - none touch Cowork, n8n, Make,
Zapier, or subscription-only environments. That is the defensible
wedge. Wrote `docs/roadmap.md` with 6 phases plus parallel consultancy
lane: Phase 0 personal-tool hardening (2 wks, close calibration loop +
ingest 15 sessions), Phase 1 API proxy MVP (4-6 wks, the precision
layer that unlocks honest EUR claims), Phase 2 insights engine v1 (3-4
wks, 5 starter rules grounded in real data not generic tips), Phase 3
agentic workflow ingestion (6-8 wks, n8n + Make + Cowork-at-scale +
subscription scrapers - this is the moat), Phase 4 OSS proxy release
(brand rename almost certainly needed - "BurnRate" is taken in this
space), Phase 5 paid insights tier with anchor pricing slightly under
getburnrate.io, Phase 6 audits + talks running parallel from Phase 2
onward. Roadmap includes decision gates with concrete pull-the-plug
criteria at each phase end, Year 1 revenue sketch (12-20k EUR
plausibility), and explicit "what we are NOT doing" list to prevent
scope drift. Did not write any code this session - this was strategy +
planning only. Next concrete action this week per the roadmap: one more
Cowork ingest pass to reach 8 sessions, fresh claude.ai snapshot,
formalize `docs/calibration.md`. Productisation question (rename, OSS
vs source-available split, hosting) deferred to before Phase 4.

---

## 2026-05-06 (later) - claude.ai snapshots store + Pro/Team usage view added

Wilco confirmed account topology: ZND personal account on platform.claude.com
(API console, currently only cipher-n8n key) and ZND personal account on
claude.ai (Pro plan, drives all hub + project chats). Web search confirmed
Anthropic does not expose token-level usage for Pro/Team subscribers - the
Usage and Cost Admin API is gated to organization-tier accounts only. The
Pro Settings -> Usage page exposes only weekly-percent bars + a metered
Extra Usage euro figure (overflow billed at API rates). Captured Wilco's
current screenshot as first snapshot: Pro plan, weekly all_models 100% used
(cap hit by Wed afternoon), EUR 82.66 spent of EUR 100 monthly cap (83%
used, resets Jun 1), EUR 12.39 balance, auto-reload off. Derived ~64.9M
token-equivalent for the overflow portion at default rates (EUR/USD 1.10,
USD 1.40 effective per million for mostly-cached Sonnet 4.6). Built
src/claude_ai_tracker.py (add/list/summary commands, configurable rates
via db/claude_ai_settings.json). Added new dashboard section with 4-card
stat grid (Weekly bucket %, Extra usage EUR, Token-equivalent, EUR/day
when 2+ snapshots exist) plus full snapshots table. Three streams now in
the dashboard, clearly labeled and not summed: Cowork estimates, API
measurements, claude.ai snapshots. Tooling note: dashboard_template.html
got corrupted by Edit on FUSE mount during this iteration; rewrote whole
file via bash heredoc to recover - same lesson as earlier sessions. Files
written: src/claude_ai_tracker.py (8.9KB), db/claude_ai_tracking.json (1
snapshot), updated render_dashboard.py + dashboard_template.html, dashboard
now 66KB.

---


## 2026-05-06 (later, hub Opus chat continued) - API CSVs imported, prompt caching insight surfaced

Wilco uploaded two Anthropic console CSV exports (April + May 2026, 33
days, cipher-n8n API key). Built `src/api_import.py` to parse them
into `db/api_daily.json` + `db/api_summary.json`. Headline insight
from the data: **86.0% of CIPHER's API input tokens came from cache
hits** (8.26M of 9.6M input). Effective API cost is ~10% of what the
raw 9.78M total billed suggests - prompt caching is doing massive
work on the n8n flows. Updated dashboard with new API-actual section
(summary banner + 4 stat cards + per-day table with cache-share
column), updated findings.md with new ranking that includes
investigating Haiku flows showing 0% cache hits across 33 days.
Hard rule (NOT applied to calibration_local.md): API actual data is
a SEPARATE billing stream from Cowork chat estimates - they shouldn't
be summed and the API CSV cannot be used as a Cowork calibration
anchor (apples vs oranges). Dashboard now shows both streams clearly
labeled. New script: `src/api_import.py` (handles multiple CSVs,
aggregates per date/key/model). Files written: `db/api_daily.json`
(53 records), `db/api_summary.json`, `db/api_usage/*.csv` (raw
exports), `dashboard/dashboard.html` rebuilt at 59KB. Productisation
note added to findings: per-key cache-hit-rate trend view and
prompt-cache-eligibility auditor are now both shippable Phase 3
features with hard evidence behind them.

---


## 2026-05-06 — Kickoff (hub chat)

Project bootstrapped from hub kickoff session. Decided BurnRate gets its
own sibling folder (5th ZND project) rather than being buried in
`hub/04_engineering/`. Confirmed Phase 1 scope: Cowork session estimator
first because Wilco hits subscription limits regularly there; API proxy
deferred to Phase 2 because API-driven projects (CIPHER, JARVIS) aren't
yet burning much. Build-for-self-first agreed; productization deferred
until we have findings to sell. Documented the hard constraint that
Cowork blocks raw-session-log access — `mcp__session_info__read_transcript`
returns summarized text without tool I/O payloads, so Phase 1 must use
calibrated estimation, not measurement. Wrote CLAUDE.md, README.md, this
log, methodology doc, schema, projects.py tagger, token_calc.py
estimator, cowork_estimator.py CLI, ingest_helper.md (how Claude feeds
transcripts in), .gitignore, requirements.txt. Dashboard HTML pending.
First real ingest pending. Hub portfolio update pending.

## 2026-06-07 (continued) — Local db path, --db-dir arg, skill finding

Three items resolved from previous session continuation. (1) **`/log-time-from-sessions` skill finding**: sessions.json path is correct (`BurnRate\db\sessions.json`). Git repo paths in Step 3 are stale — hardcoded to old sandbox session ID `busy-eager-dirac`; current session is `wizardly-blissful-allen`. The sandbox session name changes with every Cowork restart so these paths will always drift. Skill files are read-only from within Cowork; user must edit via Settings → Capabilities. Suggest replacing the hardcoded `/sessions/<name>/mnt/` paths with a dynamic lookup (`ls /sessions/ | grep -v lost | tail -1` pattern). (2) **`--db-dir` CLI arg added to `cowork_estimator.py`**: new `--db-dir <path>` argument in `main()` overrides `cfg["db_dir"]` after `load_config()`. Allows bat to write to a local path without touching `config.json`. Change written via bash/tmp to avoid FUSE truncation. (3) **`run_ingest.bat` updated with local db write path**: bat now sets `LOCAL_DB=%LOCALAPPDATA%\BurnRate\db`, syncs read-side files from OneDrive → local before ingest (ingest_state.json, claude_ai_tracking.json, api_daily/summary.json), runs all four commands with `--db-dir "%LOCAL_DB%"`, then copies ingest-written files (sessions/turns/daily_totals/forecast/ingest_state.json) back to OneDrive after render. `claude_ai_tracking.json` intentionally excluded from the write-back copy (sandbox owns it). LOG stays on OneDrive. Race condition permanently resolved — bat and sandbox no longer both write to the same FUSE-mounted files.
