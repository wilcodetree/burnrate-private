"""
cowork_estimator.py - Phase 1 BurnRate CLI (JSON storage).

Reads raw Cowork session transcripts (dumped by Claude into
db/raw_transcripts/<session_id>.json), parses turns, estimates tokens,
writes to JSON files in db/.

Usage:
    python src/cowork_estimator.py init
    python src/cowork_estimator.py ingest [session_id]
    python src/cowork_estimator.py rollup
    python src/cowork_estimator.py calibrate
    python src/cowork_estimator.py report
"""

from __future__ import annotations
import argparse
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from token_calc import (
    estimate_session, session_summary,
    SYSTEM_PROMPT_EST_TOKENS_DEFAULT, CHARS_PER_TOKEN_DEFAULT,
)
from projects import tag_session

DB_DIR = ROOT / "db"
RAW_DIR = DB_DIR / "raw_transcripts"

SESSIONS_JSON = DB_DIR / "sessions.json"
TURNS_JSON = DB_DIR / "turns.json"
DAILY_JSON = DB_DIR / "daily_totals.json"
CALIBRATION_JSON = DB_DIR / "calibration.json"
META_JSON = DB_DIR / "meta.json"


def _load(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def init_store():
    DB_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    if not SESSIONS_JSON.exists():
        _save(SESSIONS_JSON, [])
    if not TURNS_JSON.exists():
        _save(TURNS_JSON, [])
    if not DAILY_JSON.exists():
        _save(DAILY_JSON, [])
    if not CALIBRATION_JSON.exists():
        _save(CALIBRATION_JSON, [])
    if not META_JSON.exists():
        _save(META_JSON, {
            "schema_version": "1-json",
            "chars_per_token": CHARS_PER_TOKEN_DEFAULT,
            "system_prompt_est_tokens": SYSTEM_PROMPT_EST_TOKENS_DEFAULT,
            "created_ts": datetime.now(timezone.utc).isoformat(),
        })
    print(f"[OK] BurnRate JSON store initialized at {DB_DIR}")


def get_meta():
    return _load(META_JSON, {})


ROLE_LINE_RE = re.compile(r"^\[(user|assistant)\]\s?(.*)$")
TOOL_CALL_RE = re.compile(r"^\(called\s+([A-Za-z0-9_:.\-]+)\)$")


def parse_transcript(text):
    turns = []
    cur_role = None
    cur_text = []
    cur_tools = []

    def flush():
        nonlocal cur_role, cur_text, cur_tools
        if cur_role is None:
            return
        turns.append({
            "role": cur_role,
            "text": "\n".join(cur_text).strip(),
            "tool_calls": list(cur_tools),
        })
        cur_role, cur_text, cur_tools = None, [], []

    for raw_line in text.splitlines():
        line = raw_line.rstrip("\r")
        m = ROLE_LINE_RE.match(line)
        if not m:
            if cur_role is not None:
                cur_text.append(line)
            continue

        role, content = m.group(1), m.group(2)
        if cur_role is None:
            cur_role = role
        elif role != cur_role:
            flush()
            cur_role = role

        content_stripped = content.strip()
        tcm = TOOL_CALL_RE.match(content_stripped)
        if tcm:
            cur_tools.append(tcm.group(1))
        elif content_stripped:
            cur_text.append(content)

    flush()
    return turns


def ingest_one(raw):
    session_id = raw["session_id"]
    title = raw.get("title")
    cwd = raw.get("cwd")
    is_active = bool(raw.get("is_active"))
    captured_ts = raw.get("captured_ts") or datetime.now(timezone.utc).isoformat()

    transcript_text = raw.get("transcript_text", "") or ""
    turns = parse_transcript(transcript_text)
    first_user_msg = next((t["text"] for t in turns if t["role"] == "user"), "")
    project, conf = tag_session(title=title, cwd=cwd, first_user_msg=first_user_msg)

    meta = get_meta()
    chars_per_token = float(meta.get("chars_per_token", CHARS_PER_TOKEN_DEFAULT))
    sys_prompt_est = int(meta.get("system_prompt_est_tokens", SYSTEM_PROMPT_EST_TOKENS_DEFAULT))

    estimates = estimate_session(turns, system_prompt_est_tokens=sys_prompt_est, chars_per_token=chars_per_token)
    summary = session_summary(estimates)

    session_row = {
        "session_id": session_id,
        "title": title,
        "cwd": cwd,
        "project": project,
        "project_confidence": conf,
        "first_seen_ts": captured_ts,
        "last_ingest_ts": captured_ts,
        "turn_count": len(estimates),
        "is_active": is_active,
        "est_input_tokens": summary["est_input_tokens"],
        "est_output_tokens": summary["est_output_tokens"],
        "est_total_tokens": summary["est_total_tokens"],
        "est_unique_content_tokens": summary["est_unique_content_tokens"],
        "history_overhead_tokens": summary["history_overhead_tokens"],
        "history_overhead_share": summary["history_overhead_share"],
    }

    turn_rows = []
    for est in estimates:
        turn_rows.append({
            "session_id": session_id,
            "turn_index": est.turn_index,
            "turn_ts": captured_ts,
            "role": est.role,
            "user_msg_chars": est.user_msg_chars,
            "assistant_msg_chars": est.assistant_msg_chars,
            "tool_call_count": len(est.tool_calls),
            "tool_calls": est.tool_calls,
            "est_user_tokens": est.est_user_tokens,
            "est_assistant_tokens": est.est_assistant_tokens,
            "est_tool_io_tokens": est.est_tool_io_tokens,
            "est_turn_total_tokens": est.est_turn_total_tokens,
            "est_input_tokens_billed": est.est_input_tokens_billed,
            "est_output_tokens_billed": est.est_output_tokens_billed,
        })

    return {"session": session_row, "turns": turn_rows}


def ingest_all(only_session_id=None):
    DB_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    if not META_JSON.exists():
        init_store()

    files = sorted(RAW_DIR.glob("*.json"))
    if only_session_id:
        files = [f for f in files if f.stem == only_session_id]
        if not files:
            print(f"[ERR] No raw transcript for {only_session_id}")
            return
    if not files:
        print(f"[INFO] No raw transcripts in {RAW_DIR}")
        return

    sessions = _load(SESSIONS_JSON, [])
    turns = _load(TURNS_JSON, [])
    sessions_by_id = {s["session_id"]: s for s in sessions}

    n_ok = 0
    for f in files:
        try:
            raw = json.loads(f.read_text(encoding="utf-8"))
            result = ingest_one(raw)
            sid = result["session"]["session_id"]
            sessions_by_id[sid] = result["session"]
            turns = [t for t in turns if t["session_id"] != sid] + result["turns"]
            s = result["session"]
            print(f"[OK]   {sid:40} project={s['project']:8} "
                  f"turns={s['turn_count']:3} "
                  f"input~{s['est_input_tokens']:>9,} "
                  f"output~{s['est_output_tokens']:>7,} "
                  f"hist={s['history_overhead_share']*100:5.1f}%")
            n_ok += 1
        except Exception as e:
            print(f"[ERR]  {f.name}: {e}")

    sessions = list(sessions_by_id.values())
    _save(SESSIONS_JSON, sessions)
    _save(TURNS_JSON, turns)

    rollup_daily()
    print(f"\nIngested {n_ok} session(s).")


def rollup_daily():
    sessions = _load(SESSIONS_JSON, [])
    rows = {}
    for s in sessions:
        date = (s.get("last_ingest_ts") or "")[:10]
        if not date:
            continue
        proj = s.get("project", "other")
        key = (date, proj)
        r = rows.setdefault(key, {
            "date": date, "project": proj,
            "sessions": 0, "turns": 0,
            "est_input_tokens": 0, "est_output_tokens": 0,
            "est_total_tokens": 0,
        })
        r["sessions"] += 1
        r["turns"] += s.get("turn_count", 0)
        r["est_input_tokens"] += s.get("est_input_tokens", 0)
        r["est_output_tokens"] += s.get("est_output_tokens", 0)
        r["est_total_tokens"] += s.get("est_total_tokens", 0)

    daily = sorted(rows.values(), key=lambda r: (r["date"], -r["est_total_tokens"]))
    _save(DAILY_JSON, daily)
    print("[OK] daily_totals.json rebuilt.")


def report():
    sessions = _load(SESSIONS_JSON, [])
    daily = _load(DAILY_JSON, [])

    print("=" * 72)
    print(" BurnRate - current state")
    print("=" * 72)

    by_proj = defaultdict(lambda: {"n": 0, "turns": 0, "tokens": 0})
    for s in sessions:
        b = by_proj[s.get("project", "other")]
        b["n"] += 1
        b["turns"] += s.get("turn_count", 0)
        b["tokens"] += s.get("est_total_tokens", 0)

    print("\nSessions by project:")
    for proj, b in sorted(by_proj.items(), key=lambda kv: -kv[1]["tokens"]):
        print(f"  {proj:10} {b['n']:4} sessions  {b['turns']:6} turns  {b['tokens']:>14,} tokens")

    print("\nDaily totals (top 30):")
    print(f"  {'date':12} {'project':10} {'sessions':>8} {'tokens':>14}")
    for row in sorted(daily, key=lambda r: (r["date"], -r["est_total_tokens"]), reverse=True)[:30]:
        print(f"  {row['date']:12} {row['project']:10} {row['sessions']:>8} {row['est_total_tokens']:>14,}")

    print("\nTop 10 burner sessions:")
    top = sorted(sessions, key=lambda s: -s.get("est_total_tokens", 0))[:10]
    for s in top:
        title = (s.get("title") or "")[:50]
        print(f"  {s.get('est_total_tokens', 0):>12,}  "
              f"hist={s.get('history_overhead_share', 0)*100:5.1f}%  "
              f"[{s.get('project', 'other'):8}]  "
              f"{s['session_id'][:30]}  {title}")


def calibrate():
    cal_md = ROOT / "docs" / "calibration_local.md"
    if not cal_md.exists():
        print(f"[INFO] No {cal_md} - create it with daily totals from your Anthropic console / Claude usage view.")
        return

    daily = _load(DAILY_JSON, [])
    daily_by_date = defaultdict(int)
    for r in daily:
        daily_by_date[r["date"]] += r["est_total_tokens"]

    cal = _load(CALIBRATION_JSON, [])
    cal_by_date = {c["date"]: c for c in cal}

    line_re = re.compile(r"^(\d{4}-\d{2}-\d{2})\s*:\s*([\d,]+)\s*tokens")
    captured = 0
    for line in cal_md.read_text(encoding="utf-8").splitlines():
        m = line_re.match(line.strip())
        if not m:
            continue
        date = m.group(1)
        actual = int(m.group(2).replace(",", ""))
        est = daily_by_date.get(date, 0)
        factor = (actual / est) if est else None
        cal_by_date[date] = {
            "date": date,
            "actual_total_tokens": actual,
            "estimated_total_tokens": est,
            "correction_factor": factor,
            "captured_ts": datetime.now(timezone.utc).isoformat(),
        }
        captured += 1
        ratio_str = f"{factor:.3f}" if factor else "n/a"
        print(f"[CAL] {date}: actual={actual:>11,}  est={est:>11,}  factor={ratio_str}")

    _save(CALIBRATION_JSON, sorted(cal_by_date.values(), key=lambda c: c["date"]))
    print(f"[OK] Captured {captured} calibration row(s).")


def main():
    p = argparse.ArgumentParser(description="BurnRate Cowork estimator (JSON store)")
    p.add_argument("cmd", choices=["init", "ingest", "rollup", "calibrate", "report"])
    p.add_argument("session_id", nargs="?", default=None)
    args = p.parse_args()

    if args.cmd == "init":
        init_store()
    elif args.cmd == "ingest":
        if not META_JSON.exists():
            init_store()
        ingest_all(only_session_id=args.session_id)
    elif args.cmd == "rollup":
        rollup_daily()
    elif args.cmd == "calibrate":
        calibrate()
    elif args.cmd == "report":
        report()


if __name__ == "__main__":
    main()
