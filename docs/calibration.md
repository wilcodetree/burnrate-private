# Calibration

The BurnRate Cowork estimator approximates token burn from
visible-text-plus-tool-call-counts. To turn approximations into
useful absolute numbers, we calibrate against Anthropic's reported
totals.

## How to capture Anthropic console totals

1. Go to [console.anthropic.com/usage](https://console.anthropic.com/usage)
   (for API usage) or your Claude Pro / Team usage view (for Claude
   Desktop / Cowork sessions).
2. Read the daily totals for the dates BurnRate has ingested.
3. Append to `docs/calibration_local.md` (gitignored — may contain
   account-level data) using the format:

   ```
   2026-05-06: 1,250,000 tokens   # context: heavy hub session, 2 CIPHER, 1 JARVIS
   2026-05-05:   980,000 tokens
   ```

4. Run `python src/cowork_estimator.py --calibrate`.

## What calibration does

- Compares `sum(estimated_tokens for date)` vs `actual_tokens for date`.
- Stores a per-date correction factor in `db/burnrate.db.calibration`.
- If the multiplier drifts more than ±20% from the previous run,
  warns and asks Wilco whether to update the global tool-result
  defaults in `src/token_calc.py`.

## When to recalibrate

- After any major change in tool-call defaults (`token_calc.py`).
- Weekly, ideally.
- After a major Anthropic model/tokenizer change announced.
- Whenever the dashboard's numbers feel "off" — calibration is the
  first thing to check.

## What we'd love to do (Phase 2)

Replace this whole calibration loop with exact per-call usage data
from the API proxy. Phase 2's `cache_read_input_tokens`,
`cache_creation_input_tokens`, and `output_tokens` come straight
from Anthropic's `usage` block — no estimation, no calibration.

For Cowork sessions specifically, we'd need Anthropic to expose a
per-session usage export (currently only daily aggregates). If/when
that ships, BurnRate becomes "measurement, not estimation" for the
Cowork case too.
