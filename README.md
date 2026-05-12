# BurnRate

Token-burn observability for agentic LLM workflows. Find out where your tokens actually go — most of them aren't where you think.

Part of [ZeroNonsense.dev](../ZeroNonsense.dev/). Personal tool first, productized later.

## Status

- **v0.1 (in progress, 2026-05-06):** Cowork session estimator + dashboard.
- **v0.2 (planned):** Anthropic API proxy with exact cache-hit accounting.
- **v0.3+ (after findings):** Opinionated insights engine. Maybe sellable.

## What it does (today)

1. Reads your Claude Cowork session transcripts.
2. Estimates per-turn input/output tokens with calibrated tool-call multipliers.
3. Tags each session by project (CIPHER / JARVIS / DSI / GitHub Actions / Hub / etc.).
4. Stores in SQLite.
5. Renders a dashboard showing: tokens by project, top burner sessions, the per-turn cumulative-input curve, and "history overhead share" (how much of your spend is re-reading the same context).

## Why

Long agentic chats are dominated by *re-sent context*, not new work. Often 90%+ of token spend by turn 30. Without measurement, every mitigation is guesswork.

## License

TBD (will be MIT or Apache-2.0 once we open-source the proxy in Phase 2).
