"""
sync_to_onedrive.py — copy ingest-written files from local db to the repo db
(C:\\dev\\BurnRate\\db, read by the Cowork sandbox). Name kept for Task Scheduler
compatibility; the OneDrive target was retired with the 2026-07-01 C:\\dev move.
Called by run_ingest.bat after render.
Usage: python src/sync_to_onedrive.py <local_db_path> <repo_db_path>
"""
import sys
import shutil
import pathlib

FILES = [
    "sessions.json",
    "turns.json",
    "daily_totals.json",
    "forecast.json",
    "ingest_state.json",
]

def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <local_db> <repo_db>")
        sys.exit(1)

    local  = pathlib.Path(sys.argv[1])
    remote = pathlib.Path(sys.argv[2])

    if not local.exists():
        print(f"[SYNC] ERROR: local db not found: {local}")
        sys.exit(1)

    remote.mkdir(parents=True, exist_ok=True)
    ok = 0
    for fname in FILES:
        src = local / fname
        dst = remote / fname
        if src.exists():
            shutil.copy2(str(src), str(dst))
            print(f"[SYNC] {fname}: {src.stat().st_size:,} bytes -> OK")
            ok += 1
        else:
            print(f"[SYNC] {fname}: not found in local db, skipped")

    print(f"[SYNC] Done — {ok}/{len(FILES)} files copied to repo db")


if __name__ == "__main__":
    main()
