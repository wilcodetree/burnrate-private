# Mission — BurnRate

## One-line purpose

Find out where your tokens actually go — most of them aren't where you think.

## Why this is a ZeroNonsense.dev project

Brand promise: zero nonsense advice and tooling around AI / Agentic AI.
"My agent is burning a million tokens per session and I don't know why"
is a real, painful, badly-served problem. Existing tools (Helicone,
Langfuse, OpenLLMetry) are heavyweight observability platforms aimed at
production teams running paid APIs. None of them help a solo developer
on a Claude Pro subscription understand which of their conversations is
eating the daily/weekly limits.

Voice: calm, precise, sardonic. The dashboard should not say "great
work today!" or congratulate the user for any reason. It should say
"this session burned 480k tokens and 91% of it was re-read history.
Here's what to do about it."

## The three goals (mirroring the hub)

1. **Learn by doing.** Build the tool, find Wilco's actual waste
   patterns, fix them, see if usage limits stop being a daily problem.
2. **Earn where projects allow.** Phase 2 API proxy could become a
   small SaaS — OSS proxy + paid dashboard, or a per-token-monitored
   fee. Don't optimize for revenue until findings prove the insights
   matter.
3. **Talks / advice / consultancy.** "Here's what I found measuring
   my own token burn for 8 weeks" is exactly the kind of CFP-ready
   talk ZND was built around. The findings doc *is* the talk outline.

## Non-goals

- **Multi-tenancy / accounts / billing.** Not until Phase 3 at earliest.
- **A general-purpose LLM observability platform.** That's Helicone's
  job. BurnRate is opinionated: it has views about what waste looks
  like and how to fix it.
- **Beautiful UI.** Functional dashboard, no marketing polish, until we
  decide it's worth selling.

## Success criteria for Phase 1

By the end of v0.1:

- All Claude Cowork sessions from a given window are ingested and
  tagged by ZND project.
- Dashboard shows tokens-per-project for today / 7d / 30d.
- Top 10 burner sessions are visible with their per-turn cumulative
  input curve.
- Calibration against Anthropic console total is within ±25%.
- `findings.md` exists and identifies the top 5 token sinks across
  Wilco's actual usage with concrete fixes, ordered by expected impact.
