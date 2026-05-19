# Launch Posts — BurnRate Report v1.0

> Two versions. Use whichever fits the channel.
> Replace [LINK] with the Gumroad URL before posting.

---

## Version A — ZeroNonsense.dev (LinkedIn / X, attributed)

I measured my own Claude agent spend for six weeks.

The headline number: **95–98% of effective input tokens are cache reads.**

Not 90%. Not "most of it." Ninety-five to ninety-eight.

Fresh input per turn — the actual new text you type — averages 1–3 tokens.

That means every optimization focused on what you're *sending* to the model is optimizing the wrong thing. The dominant cost driver is the accumulated history of everything you've already sent.

The session that made this concrete: 186 turns, 4 hours, 16.2 million effective input tokens. The context window grew from 23K tokens at turn 1 to 127K by turn 186. Per-turn cost grew 6×.

A session twice as long doesn't cost twice as much. It costs considerably more.

I wrote up the full findings — five measured results from ground-truth Anthropic API data, a prioritized mitigation table (the leading action saves 60–80% of cache-read volume in long sessions), and an honest list of what the data doesn't yet answer.

€19 at [LINK]. Buyers get version updates as the dataset grows.

—

Methodology note: ground-truth Anthropic API usage fields from JSONL session files. No calibration, no estimates. Small sample (4 sessions + 33 days of production pipeline). I've said that in the report.

---

## Version B — CIPHER style (anonymous, educational — for daily content pipeline)

**The 90% rule for LLM context costs is wrong.**

Real measured data from agentic AI workflows: cache reads are 95–98% of effective input. Not 90%.

What that means: the new text you type each turn is noise. 1–3 tokens on average. Everything else is the model re-reading its own history.

A 186-turn session: context grew from 23K tokens at turn 1 to 127K by turn 186. Per-turn cost grew 6×.

The implication isn't subtle. If you're running agentic workflows and you haven't audited your context window growth, you're spending 5–6× more per turn by the end of a long session than you were at the start.

The fix: `/compact` at turn 25–30. Estimated saving: 60–80% of cache-read volume.

This is one practitioner's measured data, not a universal benchmark. But it's the only concrete number I've seen published on this. If you have your own, I'd like to see them.

Full findings (5 measured results, mitigation table): [LINK] — €19.

---

## Version C — Short form (X / Bluesky, tight)

I measured my Claude agent token spend.

95–98% is cache reads. Fresh input per turn: 1–3 tokens.

A 186-turn session started at 23K tokens/turn and ended at 127K. Cost grew 6×.

The optimization everyone focuses on (what you send) is the wrong target. The dominant cost is what you've already sent.

Five findings, mitigation table, honest caveats: [LINK] — €19.

---

## Posting schedule suggestion

| Day | Channel | Version |
|---|---|---|
| Launch day | LinkedIn | Version A |
| Launch day | X/Bluesky | Version C |
| +2 days | CIPHER daily pipeline | Version B (queue as educational post) |
| +7 days | LinkedIn (follow-up) | Short response to any comments / "what I've heard from buyers" |
