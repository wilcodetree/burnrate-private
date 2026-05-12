# API proxy (Phase 2 — stub)

Not yet implemented. Phase 1 (Cowork estimator) ships first; once it
proves the insights matter, we build this.

## Scope

Thin Python wrapper around `anthropic.Anthropic()` and `openai.OpenAI()`
that:

1. Logs every API call to BurnRate's SQLite (project tag, model, timestamp,
   exact `usage.input_tokens`, `usage.output_tokens`,
   `usage.cache_read_input_tokens`, `usage.cache_creation_input_tokens`,
   tool definitions size, message count).
2. Computes `$` cost per call from the model's price card.
3. Optionally enforces budget guardrails (warn/block when daily/session
   budgets exceed thresholds).
4. Optionally rewrites requests for cache friendliness (move volatile
   fields to end, ensure stable prefix).

## Why this becomes the sellable product

- Exact numbers (no estimation).
- Drop-in for any project using Anthropic/OpenAI SDKs (CIPHER, JARVIS,
  DSI, GitHub Actions all qualify).
- The "opinionated insights" engine (next layer up) takes proxy data
  and tells you *what to do* about your spend — not just shows it.

## Open questions (to be answered after Phase 1 findings)

- Pricing model: OSS proxy + paid dashboard? Per-token-monitored fee?
  Self-hosted vs SaaS?
- Multi-tenancy when?
- Anthropic + OpenAI only, or Bedrock / Vertex / Azure too?
- Built on top of OpenLLMetry (OTel) for portability, or own protocol?

Decisions deferred. First: ship Phase 1, find waste, write findings.
