# SESSION_LOG.md — BurnRate

Most-recent on top. One paragraph per session. Append at end of each chat.

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
