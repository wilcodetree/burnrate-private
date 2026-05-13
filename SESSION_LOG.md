# SESSION_LOG.md — BurnRate

Most-recent on top. One paragraph per session. Append at end of each chat.

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
