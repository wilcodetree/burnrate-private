"""
aggregate.py - Cross-session aggregations for BurnRate Phase 1.

Computes:
  - Per-tool burn breakdown (which tools dominate your token spend)
  - Session shard "what if" simulations (savings if you'd ended at turn N)

Reads from db/{sessions,turns}.json and writes db/tool_stats.json + adds
shard_sim into each session row when re-saving sessions.json.
"""

from __future__ import annotations
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_DIR = ROOT / "db"
SESSIONS_JSON = DB_DIR / "sessions.json"
TURNS_JSON = DB_DIR / "turns.json"
TOOL_STATS_JSON = DB_DIR / "tool_stats.json"


def _load(p, default):
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def _save(p, data):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def aggregate_tools(turns):
    """
    Aggregate per-tool stats across all turns.
    Returns list of dicts sorted by est_tokens desc.
    """
    by_tool = defaultdict(lambda: {
        "tool": None,
        "calls": 0,
        "sessions": set(),
        "est_tokens": 0,
    })
    # Re-import the per-tool defaults so we estimate tokens consistently
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from token_calc import (
        estimate_tool_result_tokens, TOOL_INPUT_EST_TOKENS_DEFAULT,
    )

    for t in turns:
        tools = t.get("tool_calls", []) or []
        sid = t.get("session_id")
        for name in tools:
            r = by_tool[name]
            r["tool"] = name
            r["calls"] += 1
            r["sessions"].add(sid)
            r["est_tokens"] += (
                TOOL_INPUT_EST_TOKENS_DEFAULT + estimate_tool_result_tokens(name)
            )

    rows = []
    total_tokens = sum(r["est_tokens"] for r in by_tool.values())
    for r in by_tool.values():
        rows.append({
            "tool": r["tool"],
            "calls": r["calls"],
            "sessions_using": len(r["sessions"]),
            "est_tokens": r["est_tokens"],
            "share_of_tool_io": (r["est_tokens"] / total_tokens) if total_tokens else 0.0,
        })
    rows.sort(key=lambda r: -r["est_tokens"])
    return rows


def shard_simulate(session_turns, system_prompt_est=12000):
    """
    For one session's turns (sorted by turn_index), compute total billed
    tokens, and what total billed tokens would have been if the session
    had ended at turn N for N in [10, 15, 20, 25, 30].
    The model: when you start a fresh chat, you re-pay the system prompt
    once, then the new chat's cumulative is much smaller. We approximate
    "ending early" as: keep turns 0..N as-is, drop the rest.
    """
    if not session_turns:
        return {}

    sorted_turns = sorted(session_turns, key=lambda t: t.get("turn_index", 0))
    full_total = sum(
        (t.get("est_input_tokens_billed", 0) or 0) +
        (t.get("est_output_tokens_billed", 0) or 0)
        for t in sorted_turns
    )

    cuts = {}
    for cut in [10, 15, 20, 25, 30]:
        if len(sorted_turns) <= cut:
            cuts[f"turn_{cut}"] = {
                "applies": False,
                "would_save": 0,
                "saved_share": 0.0,
            }
            continue
        kept = sorted_turns[:cut]
        kept_total = sum(
            (t.get("est_input_tokens_billed", 0) or 0) +
            (t.get("est_output_tokens_billed", 0) or 0)
            for t in kept
        )
        saved = full_total - kept_total
        cuts[f"turn_{cut}"] = {
            "applies": True,
            "would_save": saved,
            "saved_share": (saved / full_total) if full_total else 0.0,
        }
    return {
        "full_total": full_total,
        "actual_turns": len(sorted_turns),
        "cuts": cuts,
    }


def main():
    sessions = _load(SESSIONS_JSON, [])
    turns = _load(TURNS_JSON, [])

    # Per-tool aggregation
    tool_rows = aggregate_tools(turns)
    payload = {
        "row_count": len(tool_rows),
        "total_calls": sum(r["calls"] for r in tool_rows),
        "total_est_tokens": sum(r["est_tokens"] for r in tool_rows),
        "rows": tool_rows,
    }
    _save(TOOL_STATS_JSON, payload)
    print(f"[OK] tool_stats.json rebuilt: "
          f"{payload['row_count']} distinct tools, "
          f"{payload['total_calls']} total calls, "
          f"{payload['total_est_tokens']:,} est tokens")

    # Top 10 tools to console
    if tool_rows:
        print(f"\nTop tools by burn:")
        print(f"  {'tool':40} {'calls':>6} {'sessions':>9} {'est_tokens':>12} {'share':>7}")
        for r in tool_rows[:10]:
            print(f"  {r['tool']:40} {r['calls']:>6} {r['sessions_using']:>9} "
                  f"{r['est_tokens']:>12,} {r['share_of_tool_io']*100:>6.1f}%")

    # Per-session shard simulation - attach into session rows
    turns_by_session = defaultdict(list)
    for t in turns:
        turns_by_session[t.get("session_id")].append(t)

    for s in sessions:
        sid = s["session_id"]
        s["shard_sim"] = shard_simulate(turns_by_session.get(sid, []))

    _save(SESSIONS_JSON, sessions)
    print(f"\n[OK] sessions.json updated with shard_sim for {len(sessions)} session(s)")

    # Print biggest savings opportunity
    saves = []
    for s in sessions:
        sim = s.get("shard_sim") or {}
        cuts = sim.get("cuts") or {}
        for label, info in cuts.items():
            if info.get("applies") and info.get("would_save", 0) > 0:
                saves.append((info["would_save"], info["saved_share"],
                             label, s.get("title") or s["session_id"]))
    saves.sort(reverse=True)
    if saves:
        print(f"\nTop shard-saving opportunities (would_save tokens, % saved, cut, session):")
        for save, share, label, title in saves[:5]:
            print(f"  {save:>10,}  {share*100:>5.1f}%  cut at {label:8}  {title[:50]}")


if __name__ == "__main__":
    main()
