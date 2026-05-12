# Findings - 2026-05-06 (run 3, with API actuals imported)

> Major upgrade this round: Anthropic console CSVs (April + May 2026)
> imported, giving us 33 days of MEASURED token burn for CIPHER's n8n
> flows. The Cowork side stays estimated (4 sessions ingested). The
> two streams together paint a much clearer picture.

## The single most important finding so far

**86.0% of CIPHER's API input tokens came from cache hits** (8.26M of
9.6M total input tokens, over 33 days). At Anthropic's published cache-read
pricing of ~10% of base, this means CIPHER's actual API cost is roughly
**one tenth** of what the raw token count would suggest.

This is prompt caching working exactly as designed - the n8n flows are
using stable system prompts and Claude is hitting the cache aggressively.

| Token bucket (33 days, cipher-n8n) | Tokens | Effective price multiplier |
|---|---|---|
| Input - no cache | 209k | 1.0x base |
| Input - cache writes (5m + 1h) | 1.13M | ~1.25x base |
| Input - **cache reads** | **8.26M** | **0.10x base (the win)** |
| Output | 185k | ~5x base input |
| Total input | 9.60M | (mixed) |
| Total billed | 9.78M | (mixed) |

## What that means

- **CIPHER's API spend is much lower than the raw 9.78M number suggests.**
  If we assume Sonnet 4.6 base input at $3/M and cache reads at $0.30/M:
  - Naive cost (no cache): 9.6M @ $3 = $28.80
  - Actual with caching: ~$3.75 input + ~$2.78 output = ~$6.50
  - **Caching saved ~$22 over 33 days on this API key alone.**
- **April 21 was the single biggest day** (3.79M Sonnet + 484k Opus =
  4.27M total, 90.7% cache hits). That looks like a heavy n8n run -
  worth checking what happened that day, but the cache absorbed most
  of the cost.
- **Caching only kicks in for Sonnet/Opus on cipher-n8n.** Haiku usage
  shows zero cache writes/reads across all 33 days. Either the
  Haiku-using flows have shorter prefixes (no cache benefit) or
  caching isn't enabled on those calls. Worth investigating.

## Cowork side (still estimated, unchanged from run 2)

Across 4 ingested sessions, 26 turns:

- Total estimated burn: ~595k tokens
- Avg history overhead share: 92.4%
- **Read tool dominates tool I/O at 69%** of all tool-call tokens
- Best single shard opportunity: cut CIPHER tasks session at turn 10 to
  save 101k tokens (27.5%)

The Cowork numbers can't be calibrated against the API CSV - they're
separate billing streams. Cowork uses Wilco's Claude subscription;
the API CSV is metered separately on the cipher-n8n key.

## What we know vs what we still don't

| Stream | Source | Type | Coverage |
|---|---|---|---|
| API: cipher-n8n | Anthropic CSV | MEASURED (exact) | 33 days, 4 models, daily granularity |
| Cowork: hub + projects | Session transcripts via MCP | ESTIMATED (calibratable) | 4 sessions today, partial transcripts |
| API: jarvis-cloud | not yet exported | unknown | next CSV pull |
| API: github-actions | not yet exported | unknown | next CSV pull |
| API: datastream | not provisioned | unknown | future |
| Cowork: full per-day total | not exposed by Anthropic | unmeasurable today | needs subscription-side export |

The biggest data gap is Cowork-side daily totals. Anthropic does not
expose those for Pro/Team subscribers. Until they do, the Cowork
estimates remain calibrated only against tool-default heuristics, not
against actual billing.

## Updated mitigations - now ranked by what the data actually shows

The Read insight from run 2 still stands. The new API insight reorders
the priority list:

1. **Stop re-reading the same files mid-session in Cowork chats.** (Read =
   69% of tool I/O; this is still the biggest Cowork lever.)
2. **Audit Haiku flows in CIPHER for caching opportunities.** Haiku runs
   show 0% cache hits across 33 days. Either move stable prefixes earlier
   in those prompts so they qualify, or accept that short prompts don't
   benefit. Either way: confirm by intent, don't just leave it.
3. **For new API keys** (jarvis-cloud, github-actions when they arrive):
   verify cache_control is correctly placed on stable prefixes from day 1.
   The 86% cache hit rate on cipher-n8n is the bar.
4. **Shard sessions at turn 25** (or earlier when tool-heavy). The
   shard simulator on the truncated CIPHER session showed 27.5%
   savings at a turn-10 cut.
5. **Keep CLAUDE.md files lean.** (Cumulative tax on every Cowork turn.)
6. **Prefer Grep over Read for targeted lookups.**
7. **Summarize tool outputs aggressively** (M4 from original list).
8. **Cache stable prefixes** (Phase 2 / API proxy - now demonstrably
   high-impact based on the cipher-n8n data).
9. **Route narrow tasks to Haiku.**
10. **Prune Cowork attachments.**
11. **Disable unused MCP tools per chat.**

## What this changes for productisation (Phase 3 thesis)

Two product theses just got harder evidence:

1. **"Show me my cache hit rate per API key over time"** is a
   shippable view that competitors don't make obvious. Helicone shows
   per-call traces; BurnRate's view should show per-key cache health
   trends and flag drops. The cipher-n8n CSV proves we can build
   this from Anthropic's own export.
2. **"Audit my prompts for cache-eligibility"** is the next product
   feature. Haiku flows showing 0% cache hits is a finding that, in a
   product context, would be a one-click recommendation: "your X flow
   is missing cache_control on stable prefixes; add it here."

## Caveats (updated)

- API CSV covers ONE key (`cipher-n8n`). When you pull jarvis-cloud,
  github-actions, or other keys, drop the CSV in `db/api_usage/` and
  re-run `python src/api_import.py` - the importer handles multiple
  CSVs and aggregates correctly.
- Cowork is still estimated. The 595k figure is pre-calibration. It's
  also a snapshot: only 4 sessions ingested out of 9 visible.
- Some of the largest Cowork sessions (JARVIS Proposal Rework,
  Fabric Warehouse) overflowed MCP read_transcript token budget and
  haven't been ingested. Real Cowork burn is multiplicatively higher
  than 595k.

## Next steps

1. Pull more API CSVs as more keys come online (jarvis-cloud,
   github-actions). Drop into `db/api_usage/` and re-run import.
2. Investigate why Haiku flows show 0% cache hits - is it prompt
   shape or missing cache_control directives?
3. Build chunked-read helper for big Cowork sessions that overflow
   MCP token budget.
4. Phase 2 API proxy: this is the layer that makes the cache insight
   actionable in real time, not 33 days after the fact.
