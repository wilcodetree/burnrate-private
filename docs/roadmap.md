# BurnRate — Roadmap to Super Tool and Money Maker

> Created 2026-05-12 as a follow-up to the competitive landscape analysis
> in the same chat. This is the working plan for moving BurnRate from a
> personal token-burn estimator to a defensible, sellable observability
> + insights product for agentic LLM workflows.
>
> Read `CLAUDE.md` first. Read `docs/findings.md` for the evidence base
> this plan is built on. Update `SESSION_LOG.md` when a phase milestone
> ships.

## Framing

Three guardrails before any phase work begins:

**We are not going to win head-to-head with `getburnrate.io` on Claude
Code developer cost tracking.** They already ship a Go binary, 7
providers, 46 optimization rules, $12/mo Pro and $29/seat Team. Trying
to clone that is a year of wasted effort. The wedge is the workflows
they structurally can't see: Cowork, n8n, Make, Zapier, Lindy, custom
agent loops, subscription-only environments where no JSONL exists on
disk.

**We do not ship a paid product until findings prove it's worth
selling.** Phase 0 is mandatory. The 86% cache-hit insight on
`cipher-n8n` is one strong data point; the Cowork side is 4 sessions
deep. We need calibration plus breadth before the productisation work
begins or we'll be selling generic dashboards built on a sample of one.

**Estimation is honest, measurement is precise, never confuse the two
in product copy.** Every figure shown to a future paying user must be
labeled with its source stream and a stated accuracy band. The Phase 1
proxy is what unlocks honest dollar claims.

## Target end-state (where this plan is taking us)

A two-layer product, sold against a clear positioning gap:

- **Free OSS proxy + local dashboard**: a thin Anthropic / OpenAI / OpenAI-compatible
  SDK shim that logs every call with project tags to a local SQLite. Drop-in for
  Python, Node, n8n, Make, LangChain. MIT license. PyPI + npm publish. This is
  the distribution engine, not the moat.
- **Paid cloud insights tier**: opinionated rules engine, multi-project
  reconciliation across Cowork / API / subscription streams, weekly
  digest, team view, audit reports. The moat is the rule library and
  the workflow coverage, not the proxy itself.

Positioning: **"Token observability for the agentic workflows nobody
else covers."** Cowork chats, n8n flows, Make scenarios, Zapier paths,
Lindy agents, LangChain pipelines. Plus subscription-side burn for
Claude Pro / Team / ChatGPT Plus / Cursor where there is no JSONL to
read.

## Phase 0 — Personal tool hardening

Window: now → end of May 2026 (~2 weeks). No external launch in this
phase. Goal is a Cowork estimator we'd bet money on.

**Deliverables**
1. Calibration loop closed: Cowork estimated daily totals land within
   ±20% of the claude.ai subscription EUR figure for at least 7
   consecutive days. Document the multiplier table back-solved against
   real snapshots in `docs/calibration.md`.
2. Chunked-reader for big Cowork sessions: JARVIS Proposal Rework,
   Fabric Warehouse, and any session that currently overflows
   `mcp__session_info__read_transcript`. Ingested or explicitly listed
   as out-of-scope.
3. Cowork session ingest reaches at least 15 sessions across hub,
   CIPHER, JARVIS, DSI, GitHub Actions. Ranking by burn must be stable
   across consecutive re-runs.
4. `docs/findings.md` revised once Cowork breadth is in. The Read-loop
   and history-overhead insights should hold (or be revised) on the
   broader sample.

**Exit criteria (gate to Phase 1)**
- Calibration band stated, dated, and within ±20% on rolling 7-day basis.
- At least 3 ranked findings, each pointing at a specific session /
  project / behavior, not a generic recommendation.
- No critical TODOs in `cowork_estimator.py`, `token_calc.py`, or
  `aggregate.py`.

**Risks**
- Anthropic changes the Pro/Team usage page layout, breaking the
  `claude_ai_tracker.py` snapshot capture. Mitigation: store every
  raw screenshot alongside the parsed snapshot.
- Token budget overflow on the largest Cowork sessions blocks
  ingestion. Mitigation: chunked-reader explicitly in scope here.

## Phase 1 — API proxy MVP (the precision layer)

Window: ~4–6 weeks after Phase 0 gate clears.

This is the load-bearing piece of the plan. Without ground-truth API
measurement, the insights engine in Phase 2 is just dressed-up
estimation. With it, every recommendation can quote an exact EUR figure.

**Deliverables**
1. Python proxy: `burnrate.client.Anthropic` and `burnrate.client.OpenAI`
   that wrap the official SDKs, accept a `project` kwarg, and write
   each call to a local SQLite with exact `input_tokens`,
   `output_tokens`, `cache_read_input_tokens`,
   `cache_creation_input_tokens`, model, latency, prompt hash, and
   project tag.
2. Node proxy: same surface in TypeScript for the n8n nodes and any
   Node-based agent loops.
3. n8n Custom Node wrapper: a community node that swaps in for the
   stock Anthropic / OpenAI nodes and writes to the same SQLite.
4. Drop-in tested on CIPHER's n8n flows for at least 14 days. Daily
   totals from the proxy reconcile to within ±2% of the Anthropic
   console CSV for `cipher-n8n`.
5. Migration of `src/api_proxy/` from stub README to working code.
6. Schema for `proxy_calls` table added to `db/schema.sql`. Existing
   `api_import.py` CSV path stays as a fallback / cross-check.

**Exit criteria (gate to Phase 2)**
- ±2% reconciliation against console CSV on a real workflow for 14
  consecutive days.
- Per-call cost in EUR computable for any record (model pricing table
  versioned and stored).
- Performance: proxy adds < 50ms p99 overhead vs raw SDK on a CIPHER
  flow.

**Risks**
- SDK API churn (Anthropic / OpenAI change response shape). Mitigation:
  pin SDK versions, add a contract-test suite that runs daily.
- Adoption friction. Every project owner has to swap imports.
  Mitigation: keep the shim signature byte-identical to the official
  SDK constructor; the `project` kwarg is optional.

## Phase 2 — Insights engine v1

Window: ~3–4 weeks after Phase 1 gate clears. Runs in parallel with
early Phase 3 ingestion work if bandwidth allows.

This is what turns BurnRate from a dashboard into a product. A rule is
not a recommendation; it's a triggered fact with a measured saving and
a one-line remediation.

**Rule contract**
```yaml
id: cache_hit_cliff
name: "Cache hit rate below 10% on high-input flow"
applies_to: [api_proxy]
trigger:
  cache_read_share: "< 0.10"
  input_tokens_30d: "> 100000"
severity: high
estimated_saving_eur_30d: <computed>
explanation: |
  This API key sends >100k input tokens / month but caches <10%.
  Stable prefixes are not protected by cache_control.
remediation:
  type: code_snippet
  language: python
  body: |
    messages=[{"role": "system", "content": [
      {"type": "text", "text": SYSTEM_PROMPT,
       "cache_control": {"type": "ephemeral"}}
    ]}]
points_at: # which session/project/key triggered it
  api_key: "cipher-n8n"
  flow: "haiku-classifier"
```

**Five starter rules (grounded in data we already have or will have)**
1. `cache_hit_cliff` — cache_read_share below threshold on a high-input
   key. Already evidenced on CIPHER Haiku flows.
2. `claude_md_tax` — large project CLAUDE.md re-sent across many short
   turns; flag once cumulative cost > X EUR / month.
3. `read_loop` — same file Read by tool >3 times in one Cowork session.
   Already evidenced (Read = 69% of tool I/O).
4. `model_tier_mismatch` — Opus used on tasks with short responses and
   no tool use that Haiku could plausibly handle. Tunable, with a
   confirmation step before "remediation."
5. `shard_savings` — Cowork session over N turns where simulator shows
   >20% saving by cutting at turn K. Already evidenced on truncated
   CIPHER session.

**Deliverables**
- `src/rules/` package with one file per rule, a shared `Rule` base,
  and a `run_rules.py` CLI that emits triggered rules as JSON.
- Weekly digest generator: `src/digest.py` that produces a Markdown
  digest grouped by project, ranked by EUR savings.
- Dashboard tab "Findings" that lists triggered rules and links each
  to the offending session / day / API key.

**Exit criteria (gate to Phase 3)**
- All 5 rules triggered at least once on real data (no synthetic).
- At least one rule has driven a config change in CIPHER or hub
  Cowork that produced a measurable reduction (before/after EUR
  comparison stored in `docs/findings.md`).

**Risks**
- Generic rules look like every other tool's "tips" section.
  Mitigation: every rule must point at a specific session / key / day,
  not "your usage suggests…"

## Phase 3 — Agentic workflow ingestion (the moat)

Window: ~6–8 weeks, overlaps with the back half of Phase 2.

This is where we go where the competitors can't. None of them ingest
n8n, Make, Zapier, Lindy, or Cowork. We do.

**Deliverables, in priority order**
1. **n8n execution log ingest.** Parse n8n's `execution_data`
   table or REST API output. Tag each execution to a project. Cross-check
   with API proxy records by timestamp and key.
2. **Make.com scenario history ingest.** Make exposes execution
   history as CSV / JSON; build a pull-based importer.
3. **Cowork ingestion at scale.** Chunked-reader (delivered in Phase 0)
   plus a scheduled-task wrapper that ingests new sessions daily.
4. **Subscription-side scrapers.** Headless-browser scrape of
   claude.ai/usage, chatgpt.com/usage, cursor.com/usage. Daily snapshot
   into a `subscription_snapshots` table. Strictly opt-in, credentials
   stay local.
5. **Zapier task history ingest.** Lower priority; less data exposed,
   smaller user base inside the target segment.
6. **LangChain / LlamaIndex callback handler.** A `BurnRateCallbackHandler`
   that logs every LLM call into the same SQLite as the proxy.

**Exit criteria (gate to Phase 4)**
- At least 3 of the above 6 ingesters running in production on Wilco's
  own workflows.
- A single dashboard view reconciles all 3 streams (proxy, ingester,
  subscription scraper) into one project-by-project EUR figure.

**Risks**
- Subscription scrapers are fragile. Mitigation: ship them as opt-in,
  versioned, with a clear "broken because Anthropic changed the page"
  failure mode.
- Make / Zapier TOS for automated scraping. Mitigation: use their
  official APIs where they exist; don't scrape where they don't.

## Phase 4 — OSS release of the proxy

Window: ~4 weeks. Can begin as soon as Phase 1 is stable; doesn't have
to wait for Phase 3 completion.

The proxy is the distribution engine. Free, MIT, install in 30
seconds. Insights stay paid (Phase 5). The proxy alone will not make
money — that's fine. The proxy gets BurnRate installed on enough
machines that the paid tier has a path to acquisition.

**Deliverables**
1. PyPI package `burnrate-proxy`. Single-command install. Quickstart
   in README under 5 minutes from install to first logged call.
2. npm package `@burnrate/proxy`. Same surface for Node.
3. n8n Community Node, published to the n8n community catalog.
4. Public docs site (Vercel or GitHub Pages). Sections: install,
   wrap-your-SDK, view-the-dashboard, what-the-paid-tier-adds.
5. Brand: a name + logo + landing page that's screenshot-worthy.
   Tone reference: gammaglitch's `getburnrate.vercel.app` page is the
   right level of personality; `getburnrate.io` is the right level of
   professionalism. Aim between them.
6. Launch posts: Hacker News, r/LocalLLaMA, r/ClaudeAI, n8n community
   forum, LinkedIn (ZND personal), Anthropic Discord if appropriate.
7. Decision: register a permanent domain (the `burnrate.*` namespace
   is mostly taken; consider a name that survives a trademark
   collision with `getburnrate.io`).

**Naming risk**
- "BurnRate" is now used by at least 3 other projects in this exact
  space. The internal codename can stay, but the public product
  almost certainly needs a different name. Decide before launch, not
  after.

**Exit criteria (gate to Phase 5)**
- 100+ proxy installs (PyPI + npm + n8n downloads combined) within
  60 days of launch, or a clear reason why the launch underperformed
  before doubling down.
- At least 5 unsolicited issues / PRs / Discord conversations from
  real external users.

## Phase 5 — Paid insights tier

Window: ~6–8 weeks after Phase 4 launch and the 60-day adoption check.

If Phase 4 hits its exit criteria, build the paid tier. If it doesn't,
go back to Phase 3 and look for the workflow segment we're missing.

**Deliverables**
1. Cloud sync (optional, opt-in). Local SQLite stays the source of
   truth; cloud is a mirror.
2. Hosted multi-project dashboard at a permanent domain.
3. Stripe billing: free / Pro / Team tiers. Suggested anchor pricing:
   Pro $9/mo (undercut `getburnrate.io` $12), Team $24/seat (undercut
   $29). Anchor only; iterate after first 20 customers.
4. License key validation flow mirroring `getburnrate.io`'s approach
   (offline grace period, env var override, config file).
5. Privacy guarantee: never sync raw prompts, raw responses, file
   paths, or tool inputs/outputs. Aggregates only. Document this
   prominently — it's the trust differentiator vs Helicone-style
   full-trace tools.
6. Weekly digest email shipped to all paid users automatically.
7. Auto-apply remediation for the top 3 rules (snippet patching into
   a tracked `cache_control` location, with a dry-run diff first).

**Exit criteria (sustained business)**
- 30 paying customers within 90 days of launch, or a documented
  reason to pivot positioning.
- Monthly churn < 8%.
- At least one customer case study with before/after EUR figures.

**Risks**
- `getburnrate.io` adds n8n / agentic workflow support and closes
  the gap. Mitigation: ship Phase 3 ingesters fast, write the
  positioning copy first so we're known as "the agentic one" before
  they can pivot.
- Anthropic ships first-party usage observability. Mitigation: the
  insights engine and cross-stream reconciliation still have value;
  the proxy itself is the most exposed component.

## Phase 6 — Consultancy, audits, talks (parallel from Phase 2 onward)

This is goal #3 from the kickoff brief. It doesn't need its own
window — it runs in parallel from Phase 2 onward as findings accumulate.

**Deliverables**
1. Productize `findings.md` as a paid audit deliverable: client
   installs the proxy for 14 days, BurnRate (the person doing the
   work) writes their `findings.md`. Anchor price: 1500 EUR per
   audit, 1 day of work.
2. One conference talk pitched per quarter once findings exist on
   3+ external workflows. Topics: "Where 90% of agentic AI tokens
   actually go," "How we cut a client's Claude bill by 40% in 14 days."
3. Free PDF lead magnet: "2026 Agentic AI Cost Report." Mirrors the
   `getburnrate.io/report` playbook with our data — but specifically
   for agentic/no-code workflows, not Claude Code.
4. Email course: "Cut your agentic AI bill by 40% in 5 days."
   Five lessons, each pointing at one rule from the insights engine.

**Why this matters for revenue**
- Consultancy revenue scales linearly but per-engagement margin is
  high (one day of work for 1500 EUR is the unit economics).
- Audits feed back into the rules engine — every paid engagement
  uncovers a new rule that becomes part of the product.
- Talks and content drive distribution back to Phase 4 / 5.

## Money model — rough sketch

The math has to make sense at small scale, because a solo founder
moonlighting from ZND won't sustain a 12-month build with no revenue.

**Year 1 plausibility check (12 months from today)**
- Phase 0–2: zero revenue. Cost is Wilco's time.
- Phase 3–4: zero direct revenue. First paid audits possible by
  month 6: target 2 audits at 1500 EUR = 3000 EUR.
- Phase 5: target 30 paying SaaS customers by month 12. Blended
  ARPU around 12 EUR/mo = 360 EUR/mo recurring = ~2000 EUR over
  the back half of Year 1.
- Audits / consulting Year 1: 6–10 engagements at 1500 EUR =
  9000–15000 EUR.
- **Total Year 1 revenue plausibility: 12k–20k EUR.** Not life-changing,
  but enough to prove the thesis. The shape matters more than the
  number: SaaS recurring + audit lumps + content audience growth.

**Year 2 thesis**
- SaaS recurring: 200–500 customers at blended 15 EUR/mo = 3k–7.5k
  EUR/mo.
- Audits scale to 20–40/year as audience grows.
- Talks / content revenue (sponsorships, newsletter, courses) is
  a third leg that doesn't depend on the product directly.

The audit lane is the cash buffer that funds the SaaS build. Don't
neglect it.

## What we are explicitly NOT doing

To keep focus:
- No Cursor / Copilot / Windsurf / Cline / Aider / Codex CLI parser.
  `getburnrate.io` and `AleBles/burnrate` cover that ground better.
- No real-time TUI dashboard. `ccburn` and `AleBles/burnrate` cover
  that ground.
- No OBS overlay. `gammaglitch/burnrate` owns that meme.
- No multi-tenant SaaS until Phase 5 actually starts. Until then,
  local SQLite is the entire data model.
- No team auth, SSO, RBAC, audit logs until paid customers ask for
  them. Phase 5 ships single-team, single-admin, simple.
- No browser extension or Chrome MCP integration. Out of scope.
- No fine-tuning recommendations or model-routing daemon. We
  surface the insight; we don't execute model swaps automatically
  beyond the auto-apply snippet patcher.

## Decision gates (when to pull the plug or pivot)

- **End of Phase 0**: if Cowork calibration can't get within ±30% on a
  rolling 7-day basis even with multiplier tuning, the estimation
  thesis is wrong. Pivot to API-proxy-only and drop the Cowork story
  from the product (keep it as personal-use only).
- **End of Phase 1**: if proxy adoption inside Wilco's own projects
  (CIPHER, JARVIS, DSI, GitHub Actions) doesn't happen because the
  swap is too painful, the product won't survive contact with
  external users either. Redesign the integration surface before
  proceeding.
- **End of Phase 4 + 60 days**: if proxy adoption is below 100
  installs and there are no inbound external users, the positioning
  is wrong. Stop building the paid tier; revisit positioning with
  the data we have.
- **End of Phase 5 + 90 days**: if paid customers < 10, the pricing
  or the product is wrong. Talk to every churned trial user before
  building anything new.

## What to do this week

Concrete, named, time-boxed:

1. Run one more Cowork ingest pass with the existing tooling. Get
   to 8 sessions ingested across at least 3 projects.
2. Capture a fresh `claude.ai` snapshot at end of week. We need a
   second data point to drive the calibration loop.
3. Write `docs/calibration.md` formal: target band, current
   multiplier table, how to update.
4. Skeleton out `src/api_proxy/python/` with the SDK shim signature
   (no logic yet). Decide: wrap Anthropic SDK first or build on
   `httpx` directly? The wrap approach is faster; direct httpx is
   more durable. Recommend: wrap first, replace with direct httpx
   in Phase 1 if version churn hurts.
5. Pick the public product name. Spend two hours on this and lock
   it in. "BurnRate" almost certainly needs to change for the
   public release — this should not block code work, but should be
   resolved before Phase 4.

## Open questions

These need decisions before the phases they affect, not now.

- **Language for the proxy**: Python-first is obvious (CIPHER is
  n8n + Python; LangChain is Python). Node second. Go binary
  (like `getburnrate.io`) only if Phase 4 adoption warrants it.
- **Self-hosted dashboard or browser-served-from-binary**: the
  `getburnrate.io` model (single binary serves localhost:8089) is
  the lowest-friction install. Worth copying.
- **Pricing currency**: EUR or USD as primary. EUR for Wilco's
  market, USD for the wider developer audience. Default USD,
  toggle in dashboard (mirrors `getburnrate.io` and `AleBles/burnrate`).
- **License model**: MIT for the proxy is non-negotiable. For
  the insights engine — closed-source SaaS vs. source-available
  with a commercial license — decide before Phase 5.
- **Hosting**: Vercel / Fly.io / Cloudflare Workers — pick before
  Phase 5. Don't over-engineer this.

---

*This roadmap is a living document. Update at the end of each phase
gate. Failure to hit a gate is data, not failure — write down what
happened, then revise the next phase or the plan itself.*
