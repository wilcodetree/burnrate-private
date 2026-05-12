"""
claude_ai_tracker.py - Capture and analyze claude.ai (Pro/Team) usage snapshots.

Why: claude.ai does not expose token-level usage for Pro subscribers, but the
Settings -> Usage page shows weekly-percent bars + an "Extra usage" euro
amount that's billed at API rates. This module captures those numbers as
periodic snapshots and derives approximate token-equivalents for the
overflow portion.

Storage: db/claude_ai_tracking.json (list of snapshots, append-only)

Usage:
    python src/claude_ai_tracker.py add --eur 82.66 --weekly-pct 100 \\
        --balance 12.39 --note "Wed afternoon, weekly cap hit"

    python src/claude_ai_tracker.py list

    python src/claude_ai_tracker.py summary
"""

from __future__ import annotations
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_DIR = ROOT / "db"
TRACKING_JSON = DB_DIR / "claude_ai_tracking.json"
SETTINGS_JSON = DB_DIR / "claude_ai_settings.json"

# ---- Default settings (override via claude_ai_settings.json) ------------
# These are used to convert extra-usage euros into approximate token
# equivalents. They're rough and configurable.

DEFAULT_SETTINGS = {
    "eur_to_usd_rate": 1.10,
    # Effective $/M USD for mostly-cached Sonnet 4.6 input + output mix.
    # Computed assuming: 86% cache_read input + 14% no_cache input + ~5%
    # of input volume as output. Tune via claude_ai_settings.json.
    "effective_usd_per_million_tokens": 1.40,
    # Show weekly base-bucket guess. Anthropic doesn't publish this; rough
    # community figure for Pro is "5x Free" = ~5M tokens/week. Treated as
    # a placeholder until calibrated.
    "weekly_base_tokens_estimate": 5_000_000,
    "plan_tier_default": "Pro",
}


def _load_settings():
    if SETTINGS_JSON.exists():
        try:
            user = json.loads(SETTINGS_JSON.read_text(encoding="utf-8"))
            return {**DEFAULT_SETTINGS, **user}
        except Exception:
            pass
    return DEFAULT_SETTINGS


def _load_tracking():
    if not TRACKING_JSON.exists():
        return []
    try:
        return json.loads(TRACKING_JSON.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_tracking(rows):
    DB_DIR.mkdir(parents=True, exist_ok=True)
    TRACKING_JSON.write_text(
        json.dumps(rows, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def euros_to_token_equivalent(eur, settings):
    """Convert extra-usage euros to approx token-equivalent."""
    usd = eur * settings["eur_to_usd_rate"]
    rate = settings["effective_usd_per_million_tokens"]
    return int((usd / rate) * 1_000_000) if rate else 0


def add_snapshot(args):
    settings = _load_settings()
    rows = _load_tracking()

    snap = {
        "snapshot_ts": args.ts or _now_iso(),
        "plan_tier": args.plan or settings["plan_tier_default"],
        "weekly_pct": {
            "all_models": args.weekly_pct,
            "claude_design": args.design_pct or 0,
        },
        "weekly_resets_at": args.weekly_resets,
        "daily_routine_runs": {
            "used": args.routine_used or 0,
            "cap": args.routine_cap or 5,
        },
        "extra_usage": {
            "spent_eur": args.eur,
            "monthly_cap_eur": args.cap_eur or 100.0,
            "pct_used": (round(args.eur / (args.cap_eur or 100.0) * 100, 1)
                         if args.eur else 0),
            "resets_at": args.monthly_resets,
            "current_balance_eur": args.balance or 0.0,
            "auto_reload": bool(args.auto_reload),
        },
        "derived_token_equivalent": euros_to_token_equivalent(
            args.eur or 0, settings
        ),
        "settings_snapshot": {
            "eur_to_usd_rate": settings["eur_to_usd_rate"],
            "effective_usd_per_million_tokens":
                settings["effective_usd_per_million_tokens"],
        },
        "note": args.note or "",
    }
    rows.append(snap)
    rows.sort(key=lambda r: r["snapshot_ts"])
    _save_tracking(rows)

    print(f"[OK] Snapshot stored ({len(rows)} total).")
    print(f"  ts:                    {snap['snapshot_ts']}")
    print(f"  weekly all_models:     {snap['weekly_pct']['all_models']}%")
    print(f"  extra usage spent:     EUR {snap['extra_usage']['spent_eur']}  "
          f"(of {snap['extra_usage']['monthly_cap_eur']} cap, "
          f"{snap['extra_usage']['pct_used']}% used)")
    print(f"  balance:               EUR {snap['extra_usage']['current_balance_eur']}")
    print(f"  derived token-equiv:   ~{snap['derived_token_equivalent']:,} tokens")
    print(f"     (overflow portion only; subscription bundle is opaque)")


def list_snapshots(args):
    rows = _load_tracking()
    if not rows:
        print("[INFO] No snapshots yet. Use `add` to capture one.")
        return
    print(f"{'snapshot_ts':25} {'wkly%':>6} {'EUR spent':>10} "
          f"{'EUR bal':>9} {'derived tokens':>16}  note")
    for r in rows:
        ts = (r.get("snapshot_ts") or "")[:19]
        wp = (r.get("weekly_pct") or {}).get("all_models", 0)
        eu = (r.get("extra_usage") or {})
        spent = eu.get("spent_eur", 0)
        bal = eu.get("current_balance_eur", 0)
        derived = r.get("derived_token_equivalent", 0)
        note = (r.get("note") or "")[:40]
        print(f"{ts:25} {wp:>5.0f}% {spent:>10.2f} {bal:>9.2f} {derived:>16,}  {note}")


def summary(args):
    rows = _load_tracking()
    if not rows:
        print("[INFO] No snapshots yet.")
        return
    settings = _load_settings()

    # Latest snapshot
    latest = rows[-1]
    eu = latest["extra_usage"]
    print("Latest snapshot")
    print(f"  ts:                    {latest['snapshot_ts']}")
    print(f"  plan:                  {latest['plan_tier']}")
    print(f"  weekly all_models:     {latest['weekly_pct']['all_models']}%")
    print(f"  extra usage spent:     EUR {eu['spent_eur']}  "
          f"({eu['pct_used']}% of EUR {eu['monthly_cap_eur']} cap)")
    print(f"  balance:               EUR {eu['current_balance_eur']}")
    print(f"  derived token-equiv:   ~{latest['derived_token_equivalent']:,}")
    print()
    print("Conversion settings:")
    print(f"  EUR -> USD:                     {settings['eur_to_usd_rate']}")
    print(f"  effective USD/M tokens:         {settings['effective_usd_per_million_tokens']}")
    print(f"  weekly subscription base estimate: "
          f"{settings['weekly_base_tokens_estimate']:,} tokens")
    print()
    if len(rows) >= 2:
        first = rows[0]
        delta_eur = (latest["extra_usage"]["spent_eur"] -
                     first["extra_usage"]["spent_eur"])
        from datetime import datetime
        try:
            d1 = datetime.fromisoformat(first["snapshot_ts"].replace("Z", "+00:00"))
            d2 = datetime.fromisoformat(latest["snapshot_ts"].replace("Z", "+00:00"))
            days = max(1, (d2 - d1).total_seconds() / 86400)
            burn_per_day = delta_eur / days
            print(f"Trend across {len(rows)} snapshots:")
            print(f"  span:                          {days:.1f} days")
            print(f"  EUR burn delta:                {delta_eur:.2f}")
            print(f"  EUR/day rate:                  {burn_per_day:.2f}")
        except Exception:
            pass


def main():
    p = argparse.ArgumentParser(description="claude.ai usage snapshot tracker")
    sub = p.add_subparsers(dest="cmd", required=True)

    add_p = sub.add_parser("add", help="Add a snapshot (from claude.ai Settings -> Usage)")
    add_p.add_argument("--ts", help="ISO timestamp (default: now)")
    add_p.add_argument("--plan", help="Plan tier (Pro / Team / Max)")
    add_p.add_argument("--weekly-pct", type=float, required=True,
                        help="Weekly all_models % used (0-100)")
    add_p.add_argument("--design-pct", type=float, help="Claude Design % used")
    add_p.add_argument("--weekly-resets", help="When the weekly bucket resets (e.g. 'Fri 11:00 AM')")
    add_p.add_argument("--routine-used", type=int)
    add_p.add_argument("--routine-cap", type=int)
    add_p.add_argument("--eur", type=float, required=True,
                        help="Extra usage spent in EUR")
    add_p.add_argument("--cap-eur", type=float, help="Monthly cap in EUR")
    add_p.add_argument("--monthly-resets", help="When the monthly extra bucket resets")
    add_p.add_argument("--balance", type=float, help="Current balance in EUR")
    add_p.add_argument("--auto-reload", action="store_true")
    add_p.add_argument("--note", help="Free-text note")
    add_p.set_defaults(func=add_snapshot)

    sub.add_parser("list", help="List all snapshots").set_defaults(func=list_snapshots)
    sub.add_parser("summary", help="Latest + trend").set_defaults(func=summary)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
