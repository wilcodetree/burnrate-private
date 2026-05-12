"""
render_dashboard.py - Generate BurnRate dashboard HTML with baked-in data.

Reads db/*.json and writes dashboard/dashboard.html. Open in any browser.

Usage: python src/render_dashboard.py
"""
from __future__ import annotations
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_DIR = ROOT / "db"
DASH_DIR = ROOT / "dashboard"
TEMPLATE = DASH_DIR / "dashboard_template.html"
OUT = DASH_DIR / "dashboard.html"


def load_json(p, default):
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def main():
    sessions = load_json(DB_DIR / "sessions.json", [])
    turns = load_json(DB_DIR / "turns.json", [])
    daily = load_json(DB_DIR / "daily_totals.json", [])
    calibration = load_json(DB_DIR / "calibration.json", [])
    meta = load_json(DB_DIR / "meta.json", {})
    tool_stats = load_json(DB_DIR / "tool_stats.json",
                            {"rows": [], "total_calls": 0, "total_est_tokens": 0})
    api_daily = load_json(DB_DIR / "api_daily.json", [])
    api_summary = load_json(DB_DIR / "api_summary.json", {})
    claude_ai_snapshots = load_json(DB_DIR / "claude_ai_tracking.json", [])

    payload = {
        "rendered_ts": datetime.now(timezone.utc).isoformat(),
        "sessions": sessions,
        "turns": turns,
        "daily": daily,
        "calibration": calibration,
        "meta": meta,
        "tool_stats": tool_stats,
        "api_daily": api_daily,
        "api_summary": api_summary,
        "claude_ai_snapshots": claude_ai_snapshots,
        "session_count": len(sessions),
        "turn_count": len(turns),
    }

    if not TEMPLATE.exists():
        print(f"[ERR] template missing: {TEMPLATE}", file=sys.stderr)
        sys.exit(1)

    template_html = TEMPLATE.read_text(encoding="utf-8")
    json_blob = json.dumps(payload, indent=2, ensure_ascii=False)
    rendered = template_html.replace(
        "/*BURNRATE_DATA_PLACEHOLDER*/",
        f"window.BURNRATE_DATA = {json_blob};",
        1,
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(rendered, encoding="utf-8")
    n_tools = len(tool_stats.get('rows', []))
    n_api = len(api_daily)
    n_ai = len(claude_ai_snapshots)
    print(f"[OK] Dashboard written to {OUT}  ({OUT.stat().st_size:,} bytes)")
    print(f"     {len(sessions)} Cowork session(s), {len(turns)} turns, "
          f"{n_tools} tool types, {n_api} API daily records, "
          f"{n_ai} claude.ai snapshots")


if __name__ == "__main__":
    main()
