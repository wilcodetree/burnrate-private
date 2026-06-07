"""
cowork_estimator.py - BurnRate JSONL ingester (v2, ground-truth).

Reads JSONL session files written by Claude Code / Cowork into
  ~/.claude/projects/<folder>/*.jsonl
and extracts EXACT per-turn token usage from the Anthropic API response
embedded in each assistant message. No estimation, no calibration loops.

Source folders and paths are configured in BurnRate/config.json.

Usage:
    python src/cowork_estimator.py init
    python src/cowork_estimator.py scan
    python src/cowork_estimator.py ingest [session_id]
    python src/cowork_estimator.py rollup
    python src/cowork_estimator.py forecast
    python src/cowork_estimator.py report
    python src/cowork_estimator.py calibrate
"""

from __future__ import annotations
import argparse
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from projects import tag_session

# ---------------------------------------------------------------------------
# Config + path helpers
# ---------------------------------------------------------------------------

def load_config():
    cfg_path = ROOT / "config.json"
    if not cfg_path.exists():
        return {}
    try:
        raw = json.loads(cfg_path.read_text(encoding="utf-8"))
        return {k: v for k, v in raw.items() if not k.startswith("_")}
    except Exception as e:
        print(f"[WARN] Could not read config.json: {e}")
        return {}


def get_db_dir(cfg):
    if cfg.get("db_dir"):
        return Path(cfg["db_dir"])
    return ROOT / "db"


def get_source_paths(cfg):
    base = Path(cfg.get("claude_projects_dir", Path.home() / ".claude" / "projects"))
    folders = cfg.get("source_folders", [])
    paths = []
    for folder in folders:
        p = base / folder
        if p.exists():
            paths.append(p)
        else:
            print(f"[WARN] Source folder not found (skipping): {p}")
    return paths


# ---------------------------------------------------------------------------
# JSON store helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# JSONL parsing
# ---------------------------------------------------------------------------

_TAG_RE = re.compile(r'<[^>]+>')


def _clean_title(text):
    """Strip XML/command-message tags and collapse whitespace."""
    text = _TAG_RE.sub('', text or '').strip()
    text = re.sub(r'\s+', ' ', text)
    return text[:80] if text else "(no title)"


def _extract_text(content):
    """Extract plain text from a message content field (str or list of blocks)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return " ".join(parts)
    return ""


def parse_jsonl_session(jsonl_path):
    """
    Parse a single JSONL session file.
    Returns dict with: session_id, cwd, first_user_msg, turns, models
    Each turn: uuid, timestamp, input_tokens, cache_creation_tokens,
                cache_read_tokens, output_tokens, is_sidechain, model,
                request_id, stop_reason
    """
    turns = []
    first_user_msg = ""
    cwd = None
    session_id = jsonl_path.stem
    models = set()

    try:
        lines = jsonl_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception as e:
        print(f"[ERR]  Cannot read {jsonl_path.name}: {e}")
        return None

    for raw_line in lines:
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        try:
            obj = json.loads(raw_line)
        except json.JSONDecodeError:
            continue

        msg_type = obj.get("type")

        if cwd is None and obj.get("cwd"):
            cwd = obj["cwd"]

        if not first_user_msg and msg_type == "user":
            msg = obj.get("message", {})
            if isinstance(msg, dict):
                first_user_msg = _extract_text(msg.get("content", ""))[:2000]

        if msg_type == "assistant":
            msg = obj.get("message", {})
            if not isinstance(msg, dict):
                continue
            usage = msg.get("usage", {})
            if not usage:
                continue

            model = msg.get("model", "")
            if model and model != "<synthetic>":
                models.add(model)

            turns.append({
                "uuid":                  obj.get("uuid", ""),
                "timestamp":             obj.get("timestamp", ""),
                "is_sidechain":          bool(obj.get("isSidechain", False)),
                "model":                 model,
                "request_id":            obj.get("requestId", ""),
                "stop_reason":           msg.get("stop_reason", ""),
                "input_tokens":          usage.get("input_tokens", 0),
                "cache_creation_tokens": usage.get("cache_creation_input_tokens", 0),
                "cache_read_tokens":     usage.get("cache_read_input_tokens", 0),
                "output_tokens":         usage.get("output_tokens", 0),
            })

    return {
        "session_id":      session_id,
        "cwd":             cwd,
        "first_user_msg":  first_user_msg,
        "turns":           turns,
        "models":          list(models),
    }


# ---------------------------------------------------------------------------
# Ingest logic
# ---------------------------------------------------------------------------

def _session_title(first_user_msg):
    return _clean_title((first_user_msg or "").replace("\n", " "))


def ingest_jsonl(jsonl_path):
    parsed = parse_jsonl_session(jsonl_path)
    if parsed is None:
        return None

    session_id     = parsed["session_id"]
    cwd            = parsed["cwd"] or ""
    first_user_msg = parsed["first_user_msg"]
    turns_raw      = parsed["turns"]
    models         = parsed["models"]

    empty_row = {
        "session_id": session_id, "title": _session_title(first_user_msg),
        "cwd": cwd, "project": "other", "project_confidence": 0.0,
        "first_seen_ts": datetime.now(timezone.utc).isoformat(),
        "last_ingest_ts": datetime.now(timezone.utc).isoformat(),
        "last_session_ts": None, "turn_count": 0, "models": models,
        "data_source": "jsonl",
        "input_tokens": 0, "cache_creation_tokens": 0,
        "cache_read_tokens": 0, "output_tokens": 0,
        "total_effective_input": 0, "history_overhead_share": 0.0,
        "est_input_tokens": 0, "est_output_tokens": 0, "est_total_tokens": 0,
        "est_unique_content_tokens": 0, "history_overhead_tokens": 0,
    }

    if not turns_raw:
        return {"session": empty_row, "turns": []}

    project, conf = tag_session(
        title=_session_title(first_user_msg),
        cwd=cwd,
        first_user_msg=first_user_msg,
    )

    total_input          = sum(t["input_tokens"]          for t in turns_raw)
    total_cache_creation = sum(t["cache_creation_tokens"] for t in turns_raw)
    total_cache_read     = sum(t["cache_read_tokens"]     for t in turns_raw)
    total_output         = sum(t["output_tokens"]         for t in turns_raw)
    total_effective      = total_input + total_cache_creation + total_cache_read
    overhead_share       = (total_cache_read / total_effective) if total_effective else 0.0

    timestamps = [t["timestamp"] for t in turns_raw if t["timestamp"]]
    first_ts   = min(timestamps) if timestamps else None
    last_ts    = max(timestamps) if timestamps else None
    now_iso    = datetime.now(timezone.utc).isoformat()

    session_row = {
        "session_id":             session_id,
        "title":                  _session_title(first_user_msg),
        "cwd":                    cwd,
        "project":                project,
        "project_confidence":     conf,
        "first_seen_ts":          first_ts or now_iso,
        "last_ingest_ts":         now_iso,
        "last_session_ts":        last_ts,
        "turn_count":             len(turns_raw),
        "models":                 models,
        "data_source":            "jsonl",
        "input_tokens":           total_input,
        "cache_creation_tokens":  total_cache_creation,
        "cache_read_tokens":      total_cache_read,
        "output_tokens":          total_output,
        "total_effective_input":  total_effective,
        "history_overhead_share": round(overhead_share, 4),
        "est_input_tokens":       total_effective,
        "est_output_tokens":      total_output,
        "est_total_tokens":       total_effective + total_output,
        "est_unique_content_tokens": total_input + total_cache_creation,
        "history_overhead_tokens":   total_cache_read,
    }

    turn_rows = []
    for i, t in enumerate(turns_raw):
        effective = t["input_tokens"] + t["cache_creation_tokens"] + t["cache_read_tokens"]
        turn_rows.append({
            "session_id":             session_id,
            "turn_index":             i,
            "turn_ts":                t["timestamp"],
            "uuid":                   t["uuid"],
            "request_id":             t["request_id"],
            "role":                   "assistant",
            "is_sidechain":           t["is_sidechain"],
            "model":                  t["model"],
            "stop_reason":            t["stop_reason"],
            "input_tokens":           t["input_tokens"],
            "cache_creation_tokens":  t["cache_creation_tokens"],
            "cache_read_tokens":      t["cache_read_tokens"],
            "output_tokens":          t["output_tokens"],
            "total_effective_input":  effective,
            "est_input_tokens_billed":  effective,
            "est_output_tokens_billed": t["output_tokens"],
            "user_msg_chars": 0, "assistant_msg_chars": 0,
            "tool_call_count": 0, "tool_calls": [],
            "est_user_tokens": 0, "est_assistant_tokens": 0,
            "est_tool_io_tokens": 0,
            "est_turn_total_tokens": effective + t["output_tokens"],
        })

    return {"session": session_row, "turns": turn_rows}


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_init(cfg):
    db_dir = get_db_dir(cfg)
    db_dir.mkdir(parents=True, exist_ok=True)
    for fname, default in [
        ("sessions.json",     []),
        ("turns.json",        []),
        ("daily_totals.json", []),
        ("calibration.json",  []),
        ("ingest_state.json", {}),
        ("forecast.json",     {}),
        ("meta.json", {
            "schema_version": "2-jsonl",
            "data_source":    "jsonl",
            "created_ts":     datetime.now(timezone.utc).isoformat(),
        }),
    ]:
        p = db_dir / fname
        if not p.exists():
            _save(p, default)
    print(f"[OK] BurnRate store initialized at {db_dir}")


def cmd_scan(cfg):
    db_dir       = get_db_dir(cfg)
    state        = _load(db_dir / "ingest_state.json", {})
    source_paths = get_source_paths(cfg)

    if not source_paths:
        print("[INFO] No source folders found. Check config.json -> source_folders.")
        return

    total_files, total_new, total_turns = 0, 0, 0

    for src in source_paths:
        jsonl_files = sorted(src.glob("*.jsonl"))
        print(f"\nFolder: {src}")
        print(f"  {len(jsonl_files)} JSONL files found")
        for f in jsonl_files:
            mtime  = f.stat().st_mtime
            sid    = f.stem
            known  = state.get(sid, {})
            is_new = (known.get("last_mtime", 0) != mtime)
            flag   = "NEW  " if is_new else "known"
            turns  = known.get("turn_count", "?")
            size_kb = f.stat().st_size // 1024
            print(f"  [{flag}] {sid[:36]}  {size_kb:>5} KB  turns={turns}")
            total_files += 1
            if is_new:
                total_new += 1
            if isinstance(turns, int):
                total_turns += turns

    print(f"\nSummary: {total_files} files, {total_new} new/updated, {total_turns} turns ingested")


def cmd_ingest(cfg, only_session_id=None):
    db_dir       = get_db_dir(cfg)
    source_paths = get_source_paths(cfg)

    if not source_paths:
        print("[ERR] No source folders found. Check config.json -> source_folders.")
        return

    if not (db_dir / "sessions.json").exists():
        cmd_init(cfg)

    state        = _load(db_dir / "ingest_state.json", {})
    sessions     = _load(db_dir / "sessions.json", [])
    turns        = _load(db_dir / "turns.json", [])
    sessions_map = {s["session_id"]: s for s in sessions}

    n_ok, n_skip = 0, 0

    # Load manual project overrides (survive re-ingest)
    overrides_path = db_dir / "project_overrides.json"
    project_overrides = json.loads(overrides_path.read_text()) if overrides_path.exists() else {}


    for src in source_paths:
        jsonl_files = sorted(src.glob("*.jsonl"))
        if only_session_id:
            jsonl_files = [f for f in jsonl_files if f.stem == only_session_id]
            if not jsonl_files:
                print(f"[ERR] Session {only_session_id} not found in {src}")
                continue

        for f in jsonl_files:
            sid   = f.stem
            mtime = f.stat().st_mtime

            if state.get(sid, {}).get("last_mtime") == mtime:
                n_skip += 1
                continue

            result = ingest_jsonl(f)
            if result is None:
                print(f"[ERR]  {f.name}: parse failed")
                continue

            s = result["session"]
            sessions_map[sid] = s
            if sid in project_overrides:
                ov = project_overrides[sid]
                s["project"] = ov["project"]
                s["project_confidence"] = ov.get("confidence", 0.5)
                s["retag_note"] = ov.get("note", "manual override")
            turns = [t for t in turns if t["session_id"] != sid] + result["turns"]
            state[sid] = {
                "last_mtime":     mtime,
                "last_ingest_ts": datetime.now(timezone.utc).isoformat(),
                "turn_count":     s["turn_count"],
            }

            cache_pct = s["history_overhead_share"] * 100
            print(
                f"[OK]   {sid[:36]}  project={s['project']:8}  "
                f"turns={s['turn_count']:4}  "
                f"output={s['output_tokens']:>8,}  "
                f"eff_input={s['total_effective_input']:>12,}  "
                f"cache={cache_pct:5.1f}%"
            )
            n_ok += 1

    # Safety guard: never overwrite sessions.json with an empty list when files
    # were all skipped (mtime unchanged). This prevents sessions_map starting
    # empty (e.g. after FUSE corruption) and silently wiping the store.
    saved_sessions = list(sessions_map.values())
    if saved_sessions or n_ok > 0:
        _save(db_dir / "sessions.json", saved_sessions)
    else:
        existing = _load(db_dir / "sessions.json", [])
        if existing:
            print("[WARN] ingest skipped all files but sessions.json has data — preserving.")
        # else both are empty, safe to write
        _save(db_dir / "sessions.json", saved_sessions)
    _save(db_dir / "turns.json",        turns)
    _save(db_dir / "ingest_state.json", state)

    cmd_rollup(cfg, silent=True)
    print(f"\nIngested {n_ok} session(s), skipped {n_skip} unchanged.")


def cmd_rollup(cfg, silent=False):
    db_dir   = get_db_dir(cfg)
    sessions = _load(db_dir / "sessions.json", [])
    rows     = {}

    for s in sessions:
        ts   = s.get("last_session_ts") or s.get("last_ingest_ts") or ""
        date = ts[:10]
        if not date:
            continue
        proj = s.get("project", "other")
        key  = (date, proj)
        r    = rows.setdefault(key, {
            "date": date, "project": proj,
            "sessions": 0, "turns": 0,
            "input_tokens": 0, "cache_creation_tokens": 0,
            "cache_read_tokens": 0, "output_tokens": 0,
            "total_effective_input": 0,
            "est_input_tokens": 0, "est_output_tokens": 0, "est_total_tokens": 0,
        })
        r["sessions"]               += 1
        r["turns"]                  += s.get("turn_count", 0)
        r["input_tokens"]           += s.get("input_tokens", 0)
        r["cache_creation_tokens"]  += s.get("cache_creation_tokens", 0)
        r["cache_read_tokens"]      += s.get("cache_read_tokens", 0)
        r["output_tokens"]          += s.get("output_tokens", 0)
        r["total_effective_input"]  += s.get("total_effective_input", 0)
        r["est_input_tokens"]       += s.get("est_input_tokens", 0)
        r["est_output_tokens"]      += s.get("est_output_tokens", 0)
        r["est_total_tokens"]       += s.get("est_total_tokens", 0)

    daily = sorted(rows.values(), key=lambda r: (r["date"], -r["total_effective_input"]))
    _save(db_dir / "daily_totals.json", daily)
    if not silent:
        print("[OK] daily_totals.json rebuilt.")


def _week_start_dt(reset_day="friday", reset_hour=11):
    """Return the most recent weekly reset as a naive local datetime."""
    day_map = {
        "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
        "friday": 4, "saturday": 5, "sunday": 6,
    }
    reset_wd = day_map.get(reset_day.lower(), 4)
    now = datetime.now()
    days_back = (now.weekday() - reset_wd) % 7
    base = now - timedelta(days=days_back)
    candidate = base.replace(hour=reset_hour, minute=0, second=0, microsecond=0)
    if candidate > now:
        candidate = candidate - timedelta(days=7)
    return candidate


def cmd_forecast(cfg):
    """Compute weekly usage vs limit and project days until limit hit."""
    db_dir       = get_db_dir(cfg)
    sessions     = _load(db_dir / "sessions.json", [])
    daily        = _load(db_dir / "daily_totals.json", [])

    weekly_limit = int(cfg.get("weekly_token_limit", 50_000_000))
    reset_day    = cfg.get("weekly_reset_day", "friday")
    reset_hour   = int(cfg.get("weekly_reset_hour", 11))

    week_start = _week_start_dt(reset_day, reset_hour)

    this_week_eff      = 0
    this_week_sessions = 0
    for s in sessions:
        if s.get("data_source") != "jsonl":
            continue
        ts = s.get("last_session_ts") or s.get("last_ingest_ts") or ""
        if not ts:
            continue
        try:
            ts_dt = datetime.fromisoformat(ts.replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception:
            continue
        if ts_dt >= week_start:
            this_week_eff      += s.get("total_effective_input", 0)
            this_week_sessions += 1

    week_pct = min(100.0, this_week_eff / weekly_limit * 100) if weekly_limit else 0

    today     = datetime.now().date()
    cutoff_7d = (today - timedelta(days=7)).isoformat()
    recent    = [r for r in daily if r.get("date", "") >= cutoff_7d and r.get("total_effective_input", 0) > 0]
    date_totals = {}
    for r in recent:
        date_totals[r["date"]] = date_totals.get(r["date"], 0) + r.get("total_effective_input", 0)
    daily_values = list(date_totals.values())
    avg_daily    = int(sum(daily_values) / len(daily_values)) if daily_values else 0

    remaining     = max(0, weekly_limit - this_week_eff)
    days_to_limit = round(remaining / avg_daily, 1) if avg_daily > 0 else None
    next_reset    = week_start + timedelta(days=7)
    days_to_reset = (next_reset - datetime.now()).total_seconds() / 86400

    forecast = {
        "computed_ts":           datetime.now(timezone.utc).isoformat(),
        "weekly_limit":          weekly_limit,
        "week_start_iso":        week_start.isoformat(),
        "this_week_eff_input":   this_week_eff,
        "this_week_sessions":    this_week_sessions,
        "week_pct":              round(week_pct, 2),
        "avg_daily_7d":          avg_daily,
        "days_to_limit":         days_to_limit,
        "days_to_reset":         round(days_to_reset, 1),
        "next_reset_iso":        next_reset.isoformat(),
        "status":                (
            "over"    if week_pct >= 100 else
            "warning" if week_pct >= 80  else
            "ok"
        ),
    }

    _save(db_dir / "forecast.json", forecast)

    print(f"[FORECAST]  Week burn : {this_week_eff:>14,} / {weekly_limit:,}  ({week_pct:.1f}%)")
    print(f"            Avg daily : {avg_daily:>14,} (7-day, {len(daily_values)} days with data)")
    if days_to_limit is not None:
        print(f"            Limit in  : {days_to_limit} days at current rate")
    else:
        print(f"            Limit in  : n/a (no recent daily data)")
    print(f"            Resets in : {days_to_reset:.1f} days  (status: {forecast['status']})")
    print(f"[OK] forecast.json written.")


def cmd_report(cfg):
    db_dir   = get_db_dir(cfg)
    sessions = _load(db_dir / "sessions.json", [])
    daily    = _load(db_dir / "daily_totals.json", [])

    print("=" * 80)
    print(" BurnRate - ground-truth token report")
    print("=" * 80)

    by_proj = defaultdict(lambda: {"n": 0, "turns": 0, "eff_input": 0, "output": 0, "cache_sum": 0})
    for s in sessions:
        b = by_proj[s.get("project", "other")]
        b["n"]         += 1
        b["turns"]     += s.get("turn_count", 0)
        b["eff_input"] += s.get("total_effective_input", 0)
        b["output"]    += s.get("output_tokens", 0)
        b["cache_sum"] += s.get("history_overhead_share", 0)

    print(f"\n{'project':10} {'sessions':>8} {'turns':>7} {'eff_input':>14} {'output':>10} {'avg_cache%':>11}")
    for proj, b in sorted(by_proj.items(), key=lambda kv: -kv[1]["eff_input"]):
        avg_cache = (b["cache_sum"] / b["n"] * 100) if b["n"] else 0
        print(f"{proj:10} {b['n']:>8} {b['turns']:>7} {b['eff_input']:>14,} {b['output']:>10,} {avg_cache:>10.1f}%")

    print("\nDaily totals (most recent 30):")
    print(f"  {'date':12} {'project':10} {'sessions':>8} {'eff_input':>14} {'output':>10} {'cache_read':>12}")
    recent = sorted(daily, key=lambda r: r["date"], reverse=True)[:30]
    for row in recent:
        print(f"  {row['date']:12} {row['project']:10} {row['sessions']:>8} "
              f"{row['total_effective_input']:>14,} {row['output_tokens']:>10,} "
              f"{row['cache_read_tokens']:>12,}")

    print("\nTop 10 highest-burn sessions:")
    top = sorted(sessions, key=lambda s: -s.get("total_effective_input", 0))[:10]
    for s in top:
        cache_pct = s.get("history_overhead_share", 0) * 100
        title     = (s.get("title") or "")[:55]
        ts        = (s.get("last_session_ts") or "")[:10]
        print(f"  {s.get('total_effective_input', 0):>14,}  cache={cache_pct:5.1f}%  "
              f"[{s.get('project', 'other'):8}]  {ts}  {title}")


def cmd_calibrate(cfg):
    db_dir      = get_db_dir(cfg)
    cal_md      = ROOT / "docs" / "calibration_local.md"
    daily       = _load(db_dir / "daily_totals.json", [])
    calibration = _load(db_dir / "calibration.json", [])

    if not cal_md.exists():
        print(f"[INFO] {cal_md} not found.")
        print("       Create it with lines like:  2026-05-12 : 2,450,000 tokens")
        return

    daily_by_date = defaultdict(int)
    for r in daily:
        daily_by_date[r["date"]] += r.get("total_effective_input", 0) + r.get("output_tokens", 0)

    cal_by_date = {c["date"]: c for c in calibration}
    line_re     = re.compile(r"^(\d{4}-\d{2}-\d{2})\s*:\s*([\d,]+)\s*tokens")
    captured    = 0

    for line in cal_md.read_text(encoding="utf-8").splitlines():
        m = line_re.match(line.strip())
        if not m:
            continue
        date   = m.group(1)
        actual = int(m.group(2).replace(",", ""))
        our    = daily_by_date.get(date, 0)
        factor = (actual / our) if our else None
        cal_by_date[date] = {
            "date":                date,
            "actual_total_tokens": actual,
            "our_total_tokens":    our,
            "correction_factor":   round(factor, 4) if factor else None,
            "note":                "actual=Anthropic console; ours=JSONL sum (eff_input+output)",
            "captured_ts":         datetime.now(timezone.utc).isoformat(),
        }
        captured += 1
        ratio_str = f"{factor:.3f}" if factor else "n/a"
        print(f"[CAL] {date}: console={actual:>12,}  ours={our:>12,}  ratio={ratio_str}")

    _save(db_dir / "calibration.json", sorted(cal_by_date.values(), key=lambda c: c["date"]))
    print(f"[OK] {captured} calibration row(s) written.")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def cmd_render(cfg):
    """
    Embed current db/*.json data into dashboard/dashboard.html as window.BURNRATE_DATA.
    This lets the dashboard work when opened as a local file (no HTTP server needed).
    The injection is idempotent — re-running strips the old block and injects fresh data.
    """
    db_dir        = get_db_dir(cfg)
    dashboard_src = ROOT / "dashboard" / "dashboard.html"

    if not dashboard_src.exists():
        print(f"[ERR] {dashboard_src} not found.")
        return

    data = {
        "sessions":   _load(db_dir / "sessions.json",          []),
        "daily":      _load(db_dir / "daily_totals.json",       []),
        "apiDaily":   _load(db_dir / "api_daily.json",          []),
        "apiSummary": _load(db_dir / "api_summary.json",        {}),
        "forecast":   _load(db_dir / "forecast.json",           {}),
        "aiTracking": _load(db_dir / "claude_ai_tracking.json", []),
        "cfg":        cfg,
        "turns":      _load(db_dir / "turns.json",              []),
        "rendered_ts": datetime.now(timezone.utc).isoformat(),
    }

    inject_start = "<!-- BURNRATE_DATA_START -->"
    inject_end   = "<!-- BURNRATE_DATA_END -->"
    inject_block = (
        f"{inject_start}\n"
        f"<script>window.BURNRATE_DATA = {json.dumps(data, separators=(',',':'))};</script>\n"
        f"{inject_end}"
    )

    html = dashboard_src.read_text(encoding="utf-8")

    # Strip any existing injection
    html = re.sub(
        re.escape(inject_start) + r".*?" + re.escape(inject_end),
        "", html, flags=re.DOTALL
    ).strip()

    # Inject before </head>
    if "</head>" not in html:
        print("[ERR] </head> not found in dashboard.html — cannot inject data.")
        return

    html = html.replace("</head>", inject_block + "\n</head>", 1)

    # Write atomically via tmp to avoid partial writes
    tmp = dashboard_src.with_suffix(".html.tmp")
    tmp.write_text(html, encoding="utf-8")
    import os as _os
    _os.replace(tmp, dashboard_src)

    session_count = len([s for s in data["sessions"] if s.get("turn_count", 0) > 0])
    print(f"[OK] dashboard.html rendered with {session_count} sessions, "
          f"{len(data['daily'])} daily rows, forecast status={data['forecast'].get('status','?')}")
    print(f"     Open: {dashboard_src}")


def cmd_snapshot(cfg, weekly_pct=None, session_pct=None, note=None):
    """
    Record a claude.ai Usage page reading (start-of-day or end-of-day screenshot).
    Stores in db/claude_ai_tracking.json and attempts to calibrate weekly_token_limit.

    Usage:
        python src/cowork_estimator.py snapshot --weekly-pct 31 --session-pct 19
        python src/cowork_estimator.py snapshot --weekly-pct 58 --note "end of day"
    """
    if weekly_pct is None:
        print("[ERR] --weekly-pct is required. Read it from claude.ai Settings -> Usage.")
        return

    db_dir   = get_db_dir(cfg)
    tracking = _load(db_dir / "claude_ai_tracking.json", [])
    sessions = _load(db_dir / "sessions.json", [])

    now_iso  = datetime.now(timezone.utc).isoformat()
    now_local = datetime.now().isoformat()

    # Current-week Cowork burn (for correlation)
    reset_day  = cfg.get("weekly_reset_day", "sunday")
    reset_hour = int(cfg.get("weekly_reset_hour", 1))
    week_start = _week_start_dt(reset_day, reset_hour)
    this_week_cowork = sum(
        s.get("total_effective_input", 0)
        for s in sessions
        if s.get("data_source") == "jsonl"
        and s.get("turn_count", 0) > 0
        and (ts := s.get("last_session_ts") or s.get("last_ingest_ts") or "")
        and _ts_ge(ts, week_start)
    )

    # Calibration: find the best prior snapshot this week to diff against.
    # "Best" = most recent snapshot where delta_pct > 0 AND delta_cowork > 0.
    implied_limit = None
    prev_used     = None
    prev_this_week = [
        t for t in tracking
        if _ts_ge(t.get("snapshot_ts", ""), week_start)
    ]
    # Walk from most-recent to oldest, pick first usable anchor
    for prev_candidate in reversed(prev_this_week):
        prev_pct    = prev_candidate.get("weekly_pct_all_models", 0)
        prev_cowork = prev_candidate.get("this_week_cowork_tokens", 0)
        delta_pct    = weekly_pct - prev_pct
        delta_cowork = this_week_cowork - prev_cowork
        if delta_pct > 0 and delta_cowork > 0 and prev_cowork > 0:
            implied_limit = int(delta_cowork / delta_pct * 100)
            prev_used = prev_candidate
            break

    entry = {
        "snapshot_ts":              now_iso,
        "snapshot_local":           now_local,
        "plan_tier":                cfg.get("plan_tier", "team"),
        "weekly_pct_all_models":    weekly_pct,
        "session_pct":              session_pct,
        "this_week_cowork_tokens":  this_week_cowork,
        "implied_weekly_limit":     implied_limit,
        "note":                     note or "",
    }
    tracking.append(entry)
    _save(db_dir / "claude_ai_tracking.json", tracking)

    print(f"[SNAPSHOT] {now_local[:16]}  weekly={weekly_pct}%"
          + (f"  session={session_pct}%" if session_pct is not None else "")
          + (f"  note={note!r}" if note else ""))
    print(f"           This-week Cowork tokens: {this_week_cowork:,}")
    if implied_limit:
        print(f"           Implied weekly limit: ~{implied_limit:,} tokens")
        print(f"           (based on +{weekly_pct-prev_used.get('weekly_pct_all_models',0):.1f}% with +{this_week_cowork-prev_used.get('this_week_cowork_tokens',0):,} Cowork tokens)")
        # Auto-update config if implied limit looks reasonable (>1M, <500M)
        if 1_000_000 < implied_limit < 500_000_000:
            current_limit = cfg.get("weekly_token_limit", 50_000_000)
            # Blend: 70% new estimate, 30% old (smoothing for noisy estimates)
            blended = int(implied_limit * 0.7 + current_limit * 0.3)
            cfg_path = Path(__file__).resolve().parent.parent / "config.json"
            if cfg_path.exists():
                try:
                    raw = json.loads(cfg_path.read_text(encoding="utf-8"))
                    raw["weekly_token_limit"] = blended
                    raw["_calibration_note"] = f"Auto-calibrated {now_local[:10]}: implied={implied_limit:,} blended={blended:,}"
                    tmp = cfg_path.with_suffix(".json.tmp")
                    tmp.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
                    import os as _os2; _os2.replace(tmp, cfg_path)
                    print(f"           Auto-updated weekly_token_limit: {current_limit:,} -> {blended:,}")
                except Exception as e:
                    print(f"           [WARN] Could not auto-update config: {e}")
    else:
        print(f"           No prior snapshot this week — calibration needs 2+ snapshots.")
    print(f"[OK] Snapshot saved ({len(tracking)} total).")


def _ts_ge(ts_str, dt_naive):
    """Return True if ts_str (ISO with optional Z/offset) >= dt_naive."""
    try:
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00")).replace(tzinfo=None)
        return dt >= dt_naive
    except Exception:
        return False


def main():
    p = argparse.ArgumentParser(description="BurnRate - JSONL-based exact token ingester (v2)")
    p.add_argument("cmd", choices=["init", "scan", "ingest", "rollup", "report", "calibrate", "forecast", "render", "snapshot"])
    p.add_argument("session_id", nargs="?", default=None, help="Ingest a single session by ID")
    p.add_argument("--weekly-pct",  type=float, default=None, help="Weekly %% from claude.ai Usage page")
    p.add_argument("--session-pct", type=float, default=None, help="Session %% from claude.ai Usage page")
    p.add_argument("--note", type=str, default=None, help="Optional note, e.g. 'start of day'")
    p.add_argument("--db-dir", type=str, default=None,
                   help="Override db/ directory (absolute path). Bat uses this to write to a local "
                        "path and avoid the OneDrive/FUSE write-collision race condition.")
    args = p.parse_args()

    cfg = load_config()
    if args.db_dir:
        cfg["db_dir"] = args.db_dir

    if args.cmd == "init":
        cmd_init(cfg)
    elif args.cmd == "scan":
        cmd_scan(cfg)
    elif args.cmd == "ingest":
        cmd_ingest(cfg, only_session_id=args.session_id)
    elif args.cmd == "rollup":
        cmd_rollup(cfg)
    elif args.cmd == "report":
        cmd_report(cfg)
    elif args.cmd == "calibrate":
        cmd_calibrate(cfg)
    elif args.cmd == "forecast":
        cmd_forecast(cfg)
    elif args.cmd == "render":
        cmd_render(cfg)
    elif args.cmd == "snapshot":
        cmd_snapshot(cfg, weekly_pct=args.weekly_pct, session_pct=args.session_pct, note=args.note)


if __name__ == "__main__":
    main()
