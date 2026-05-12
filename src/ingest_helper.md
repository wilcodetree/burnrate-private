# Ingest helper — How Claude (this chat) feeds transcripts into BurnRate

Phase 1 BurnRate cannot read raw Cowork session JSONLs (Cowork blocks
that path). Instead, Claude (in a hub or BurnRate chat) uses
`mcp__session_info` to dump session transcripts into
`db/raw_transcripts/<session_id>.json`, and then runs the estimator.

## One-shot ingest run (Claude does this)

```python
# Pseudocode for what Claude executes in the chat:

sessions = mcp__session_info__list_sessions(limit=20)

for s in sessions.sessions:
    transcript = mcp__session_info__read_transcript(
        session_id=s.id,
        format="full",
        limit=10000,           # high cap; we want the whole thing
        max_wait_seconds=0,    # don't block on running sessions
    )
    raw = {
        "session_id": s.id,
        "title": s.title,
        "cwd": s.cwd,
        "is_active": (s.status == "active"),
        "captured_ts": now_iso(),
        "transcript_text": transcript.text,
    }
    write(f"db/raw_transcripts/{s.id}.json", json.dumps(raw, indent=2))

bash("python src/cowork_estimator.py ingest")
bash("python src/cowork_estimator.py report")
```

## Why the dump-to-file step?

Two reasons:

1. **Replayability.** The estimator is deterministic; we can re-run
   it after tuning calibration without re-asking the MCP server.
2. **Debuggability.** When numbers look off, we can read the raw
   `db/raw_transcripts/<id>.json` to see exactly what Claude saw.

## Privacy

`db/raw_transcripts/` is gitignored. It contains session text including
work and personal content. Don't commit, don't share. If sharing
findings publicly, derive aggregate metrics only.

## Operating cadence (suggested)

- **Daily** during active week: one ingest pass at end of day.
- **Weekly**: capture Anthropic console totals into
  `docs/calibration_local.md`, run `calibrate`, review correction
  factors. If global factor drifts >20%, retune
  `TOOL_RESULT_DEFAULTS` in `src/token_calc.py`.
- **Monthly**: review `docs/findings.md`, archive old session dumps.
