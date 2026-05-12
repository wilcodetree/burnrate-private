"""
api_import.py - Parse Anthropic console CSV exports into BurnRate JSON store.

Reads all CSVs in db/api_usage/ and produces:
  - db/api_daily.json     : daily totals per (date, api_key, model)
  - db/api_summary.json   : grand totals + cache effectiveness summary

Source CSV schema (Anthropic console export):
  usage_date_utc, model_version, api_key, workspace, usage_type,
  context_window, usage_input_tokens_no_cache, usage_input_tokens_cache_write_5m,
  usage_input_tokens_cache_write_1h, usage_input_tokens_cache_read,
  usage_output_tokens, web_search_count, inference_geo, speed

These are MEASUREMENTS from Anthropic, not estimates - treat as ground truth.

Usage:
    python src/api_import.py
"""

from __future__ import annotations
import csv
import json
from collections import defaultdict
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent.parent
USAGE_DIR = ROOT / "db" / "api_usage"
OUT_DAILY = ROOT / "db" / "api_daily.json"
OUT_SUMMARY = ROOT / "db" / "api_summary.json"

# Map api_key -> ZND project slug (extend as more keys are added)
API_KEY_TO_PROJECT = {
    "cipher-n8n": "cipher",
    # placeholders for future keys - update when they appear in CSVs
    "jarvis-cloud": "jarvis",
    "github-actions": "gha",
    "datastream": "dsi",
    "burnrate-proxy": "burnrate",
}


def _to_int(v):
    try:
        return int(v) if v not in ("", None) else 0
    except ValueError:
        return 0


def parse_csvs():
    rows = []
    for csv_path in sorted(USAGE_DIR.glob("*.csv")):
        with csv_path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                rows.append({
                    "date": r["usage_date_utc"],
                    "model": r["model_version"],
                    "api_key": r["api_key"],
                    "workspace": r.get("workspace", ""),
                    "context_window": r.get("context_window", ""),
                    "input_no_cache": _to_int(r["usage_input_tokens_no_cache"]),
                    "cache_write_5m": _to_int(r["usage_input_tokens_cache_write_5m"]),
                    "cache_write_1h": _to_int(r["usage_input_tokens_cache_write_1h"]),
                    "cache_read":     _to_int(r["usage_input_tokens_cache_read"]),
                    "output":         _to_int(r["usage_output_tokens"]),
                    "web_searches":   _to_int(r.get("web_search_count", 0)),
                    "project":        API_KEY_TO_PROJECT.get(r["api_key"], "other"),
                    "_source_file":   csv_path.name,
                })
    return rows


def aggregate_daily(rows):
    """Aggregate to (date, api_key, project, model) granularity."""
    agg = defaultdict(lambda: {
        "input_no_cache": 0, "cache_write_5m": 0, "cache_write_1h": 0,
        "cache_read": 0, "output": 0, "web_searches": 0, "lines": 0,
    })
    for r in rows:
        key = (r["date"], r["api_key"], r["project"], r["model"])
        a = agg[key]
        a["input_no_cache"] += r["input_no_cache"]
        a["cache_write_5m"] += r["cache_write_5m"]
        a["cache_write_1h"] += r["cache_write_1h"]
        a["cache_read"] += r["cache_read"]
        a["output"] += r["output"]
        a["web_searches"] += r["web_searches"]
        a["lines"] += 1

    daily = []
    for (date, api_key, project, model), v in sorted(agg.items()):
        total_input = (v["input_no_cache"] + v["cache_write_5m"]
                       + v["cache_write_1h"] + v["cache_read"])
        total_billed = total_input + v["output"]
        cache_share = (v["cache_read"] / total_input) if total_input else 0
        daily.append({
            "date": date,
            "api_key": api_key,
            "project": project,
            "model": model,
            "input_no_cache":     v["input_no_cache"],
            "cache_write_5m":     v["cache_write_5m"],
            "cache_write_1h":     v["cache_write_1h"],
            "cache_read":         v["cache_read"],
            "output":             v["output"],
            "total_input":        total_input,
            "total_billed":       total_billed,
            "cache_read_share":   round(cache_share, 4),
        })
    return daily


def summary(daily):
    grand = {
        "input_no_cache": 0, "cache_write_5m": 0, "cache_write_1h": 0,
        "cache_read": 0, "output": 0, "rows": 0, "dates": set(),
        "models": set(), "api_keys": set(), "projects": set(),
    }
    for d in daily:
        grand["input_no_cache"] += d["input_no_cache"]
        grand["cache_write_5m"] += d["cache_write_5m"]
        grand["cache_write_1h"] += d["cache_write_1h"]
        grand["cache_read"] += d["cache_read"]
        grand["output"] += d["output"]
        grand["rows"] += 1
        grand["dates"].add(d["date"])
        grand["models"].add(d["model"])
        grand["api_keys"].add(d["api_key"])
        grand["projects"].add(d["project"])

    total_input = (grand["input_no_cache"] + grand["cache_write_5m"]
                   + grand["cache_write_1h"] + grand["cache_read"])
    return {
        "captured_ts": datetime.now(timezone.utc).isoformat(),
        "row_count": grand["rows"],
        "date_range": [min(grand["dates"]) if grand["dates"] else None,
                       max(grand["dates"]) if grand["dates"] else None],
        "days_covered": len(grand["dates"]),
        "models_seen": sorted(grand["models"]),
        "api_keys_seen": sorted(grand["api_keys"]),
        "projects_seen": sorted(grand["projects"]),
        "totals": {
            "input_no_cache": grand["input_no_cache"],
            "cache_write_5m": grand["cache_write_5m"],
            "cache_write_1h": grand["cache_write_1h"],
            "cache_read":     grand["cache_read"],
            "output":         grand["output"],
            "total_input":    total_input,
            "total_billed":   total_input + grand["output"],
        },
        "cache_read_share": (grand["cache_read"] / total_input) if total_input else 0,
    }


def main():
    if not USAGE_DIR.exists() or not list(USAGE_DIR.glob("*.csv")):
        print(f"[INFO] No CSVs in {USAGE_DIR}")
        return

    rows = parse_csvs()
    daily = aggregate_daily(rows)
    summ = summary(daily)

    OUT_DAILY.write_text(json.dumps(daily, indent=2, ensure_ascii=False),
                          encoding="utf-8")
    OUT_SUMMARY.write_text(json.dumps(summ, indent=2, ensure_ascii=False),
                            encoding="utf-8")

    print(f"[OK] Parsed {len(rows)} CSV rows from {USAGE_DIR}")
    print(f"[OK] Wrote {len(daily)} daily records to {OUT_DAILY.name}")
    print(f"[OK] Wrote summary to {OUT_SUMMARY.name}")
    print()
    print(f"Date range:    {summ['date_range'][0]} to {summ['date_range'][1]}  ({summ['days_covered']} days)")
    print(f"Models seen:   {', '.join(summ['models_seen'])}")
    print(f"API keys:      {', '.join(summ['api_keys_seen'])}")
    print(f"Projects:      {', '.join(summ['projects_seen'])}")
    print()
    t = summ['totals']
    print(f"Grand totals over {summ['days_covered']} days:")
    print(f"  input (no cache):      {t['input_no_cache']:>13,}  full price")
    print(f"  cache writes (5m+1h):  {t['cache_write_5m']+t['cache_write_1h']:>13,}  ~1.25x base")
    print(f"  cache reads:           {t['cache_read']:>13,}  ~0.10x base price (BIG SAVINGS)")
    print(f"  output:                {t['output']:>13,}")
    print(f"  TOTAL INPUT:           {t['total_input']:>13,}")
    print(f"  TOTAL BILLED:          {t['total_billed']:>13,}")
    print(f"  cache_read_share:      {summ['cache_read_share']*100:>12.1f}%  of input came from cache hits")


if __name__ == "__main__":
    main()
