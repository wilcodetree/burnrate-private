# Methodology — How BurnRate estimates token burn

> Read this before changing the estimator. The calibration model is
> intentionally conservative; do not "fix" it until you've reviewed the
> assumptions here.

## Ground truth: what we'd love to have

For each Cowork chat turn, the actual numbers we want are:

```
input_tokens          (what Anthropic billed for the request prefix)
output_tokens         (what Anthropic billed for the assistant response)
cache_read_tokens     (input served from prompt cache, ~0.1× price)
cache_creation_tokens (input written to cache, ~1.25× price)
```

Those are exposed by Anthropic's `/v1/messages` API in the `usage`
block. **Cowork does not expose them.** `mcp__session_info__read_transcript`
returns formatted text with tool calls collapsed to `(called Read)` —
no payloads, no usage block, no cache stats.

## What we have to work with

For each turn we can extract:

- **User message text** (chars)
- **Assistant message text** (chars)
- **Tool call markers** with the tool name (e.g., `(called Read)`,
  `(called mcp__workspace__bash)`)
- **Session metadata:** session_id, title, cwd, idle/active flag

That's it.

## The estimation model

### Step 1 — Visible-text tokens

For any text segment:

```
est_tokens(text) = ceil(len(text) / chars_per_token)
```

Default `chars_per_token = 3.5` (good enough for mixed English+code).
If `tiktoken` is installed, use `cl100k_base` encoding instead — it's a
closer proxy for Anthropic's tokenizer than chars-per-token. (Anthropic
uses its own tokenizer, but cl100k tends to be within ±10% for similar
content.)

Note: Anthropic has flagged that newer model tokenizers may produce up
to ~35% more tokens than older ones for the same text. The dashboard
should display a known-uncertainty band around all numbers.

### Step 2 — Tool-call overhead

Each `(called X)` marker contributes:

- A baseline tool-result size (the response Claude got back) →
  `tool_result_default_tokens[tool_name]`
- A baseline tool-input size (the args Claude sent) → small constant,
  ~50 tokens default

Initial defaults (tunable via calibration):

| Tool name pattern        | Default est. result tokens |
|--------------------------|----------------------------|
| `Read`                   | 2500                       |
| `Write`                  | 50                         |
| `Edit`                   | 100                        |
| `Glob`                   | 300                        |
| `Grep`                   | 800                        |
| `Bash` / `mcp__workspace__bash` | 600                |
| `WebFetch`               | 4000                       |
| `WebSearch`              | 1500                       |
| `mcp__session_info__*`   | 1500                       |
| `mcp__cowork__*`         | 200                        |
| `Task` / `Agent`         | 3000                       |
| `TodoWrite` / `Task*`    | 100                        |
| `mcp__visualize__*`      | 800                        |
| `AskUserQuestion`        | 200                        |
| (default for unmatched)  | 500                        |

These will be **wrong** in absolute terms. They're useful because:

- Relative ranking of tool-heavy sessions vs lightweight chats is
  reliable even when constants are off.
- Calibration (Step 3) tunes them.

### Step 3 — Cumulative input (the quadratic effect)

For each turn `t`:

```
context_at_turn(t) = system_prompt_est
                   + sum(visible text + tool I/O for turns 1..t-1)
                   + this_turn_user_message
                   + this_turn_tool_results

input_tokens_billed_at_turn(t) ≈ context_at_turn(t)
output_tokens_billed_at_turn(t) ≈ assistant_message_at_turn(t)
```

`system_prompt_est` is configurable per session-type (Cowork mode has a
~10–15k-token system prompt by inspection of the visible header). We
use `12000` by default; tuneable in `src/token_calc.py`.

This is what makes the "history overhead share" KPI meaningful — by
turn 30, `context_at_turn(t)` is dominated by re-reads.

### Step 4 — Calibration loop

Once a week (or whenever Wilco remembers), copy the daily totals from
the Anthropic console / Claude usage page into
`docs/calibration_local.md` (gitignored). Format:

```
2026-05-04: 1,250,000 tokens
2026-05-05:   980,000 tokens
2026-05-06: (in progress)
```

Run `python src/cowork_estimator.py --calibrate`. The script:

1. Sums BurnRate's estimate for each calibration date.
2. Computes the global multiplier `actual / estimated`.
3. Adjusts the tool-result default table proportionally (or stores a
   per-day correction factor).

Goal: estimator within ±25% of console totals. We don't expect ±5%
without raw transcripts.

## What we explicitly cannot measure (Phase 1)

- **Cache hits.** Cowork uses Anthropic's prompt caching transparently.
  We see total token spend (via console) but cannot tell BurnRate which
  turns hit the cache. Phase 2 (API proxy) fixes this.
- **Image/file attachment tokens.** When you attach a screenshot, that's
  ~1500–4000 tokens silently added. We can't see attachments via the
  transcript MCP. Best workaround: Wilco notes attachment-heavy
  sessions manually.
- **Sub-agent / Task tool overhead.** Spawned agents have their own
  context window with system prompts re-paid. Each `(called Task)` is
  a known under-estimate.

We list all three on the dashboard as a known-uncertainty footer.

## Why this is still useful

Even with 25–30% absolute error, the *ranking* of sessions by burn,
the *shape* of the cumulative-input curve, and the *project breakdown*
are all robust to multiplicative error. You can't tell a CFO "I burned
$X exactly" — but you can tell yourself "the JARVIS architecture chat
on Tuesday burned 8× more than the CIPHER content chat on Monday, and
here's why."

That's enough to make the next decision.
