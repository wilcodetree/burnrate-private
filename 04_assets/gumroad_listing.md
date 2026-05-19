# Gumroad Listing — BurnRate Report v1.0

> Paste-ready copy for gumroad.com. Price: €19. Brand: ZeroNonsense.dev.
> Update version number and "what's new" line when re-uploading v1.1+.

---

## Product title

**95–98%: What My Claude Agent Sessions Actually Cost**

---

## Tagline / short description (shown under title)

Real token-burn data from agentic AI workflows. Not estimates. Not vendor marketing.

---

## Full description (Gumroad product page body)

I measured my own Claude agent spend. Here's what the numbers actually show.

**The headline finding:** Cache reads are 95–98% of effective input tokens in agentic workflows — not the 90% estimate most practitioners use. Fresh input per turn averages 1–3 tokens. The dominant cost driver isn't what you're *sending* to the model. It's the accumulated history of everything you've already sent.

---

**What's inside:**

Five findings from ground-truth Anthropic API data — exact numbers from the `usage` fields embedded in session JSONL, not estimates:

1. **Cache reads are 95–98% of effective input** — measured across four sessions totalling 26.3M tokens. The 90% rule of thumb is too conservative.

2. **Session length is the compounding variable** — a 186-turn session grew from 23K tokens/turn at turn 1 to 127K by turn 186. Per-turn cost grew 6×. A session twice as long costs well over twice as much.

3. **CLAUDE.md overhead dominates cache-writes** — the system prompt + project context loaded at session start (87K–304K tokens per session) is re-read on every subsequent turn. Reducing it by 30% saves proportionally, every session.

4. **A production daily pipeline at 86% cache efficiency** — what that looks like, how it was achieved, and the one anomaly still being investigated.

5. **Project tagging and sub-agent double-counting** — the two measurement artefacts that will distort your data if you don't account for them.

Plus:

- A prioritized **mitigation table** — ranked by estimated token savings, not vibes. Leading action saves 60–80% of cache-read volume in long sessions.
- An honest **"What We're Still Measuring"** section — the three open questions the current dataset can't yet resolve.

---

**Who this is for:** Engineers and practitioners building on Anthropic's API who want real numbers rather than vendor documentation or anecdote.

**Who this is not for:** Anyone looking for a comprehensive cost calculator or benchmarks across providers. This is one person's measured data from one tool — presented precisely because it's concrete, not because it claims to be universal.

---

**Version updates:** This is v1.0, based on 4 Cowork sessions and 33 days of production pipeline data. The dataset is growing. Buyers receive v1.1+ updates automatically via Gumroad email when new data materially changes the findings.

---

## Price

**€19**

---

## Tags (Gumroad product tags)

Claude, Anthropic, LLM costs, token optimization, AI agents, agentic AI, cache tokens, context window, LLMOps, AI engineering, observability

---

## Thank-you / delivery email (paste into Gumroad "Receipt" message field)

---

Thanks for buying.

You've got v1.0 — based on 4 measured sessions and 33 days of production pipeline data from a live n8n workflow. Ground-truth Anthropic API numbers, no estimates.

When v1.1 ships (more sessions, larger sample), you'll receive the updated PDF automatically via this email address.

If the numbers surprise you, or if you run your own measurements and find something different, I'd genuinely like to hear it: wilco.de.tree@a-insights.eu

— Wilco de Tree
zerononsense.dev

---

## Gumroad setup checklist

- [ ] Upload `burnrate_report_v1_0.pdf` as the product file
- [ ] Set price to €19 (enable "Pay what you want" minimum €19 optional — wider reach)
- [ ] Set currency to EUR
- [ ] Paste title, description, tagline above
- [ ] Add cover image (use the report cover page — export page 1 as PNG at 1200px wide)
- [ ] Paste receipt message above
- [ ] Enable "Send receipt email" with PDF attachment
- [ ] Add tags above
- [ ] Publish

---

## When you publish v1.1

1. Run `python scripts/generate_report.py --version 1.1` from the BurnRate root
2. Upload new PDF to the same Gumroad product (replaces the file)
3. Use Gumroad "Email your customers" to notify existing buyers
4. Subject line: `BurnRate Report v1.1 — updated with [X new sessions / key new finding]`
