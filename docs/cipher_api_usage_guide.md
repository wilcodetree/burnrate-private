# CIPHER API Usage — How to Import into BurnRate

BurnRate measures **Cowork sessions automatically** (daily via Task Scheduler).  
CIPHER's Anthropic API usage is a **separate billing stream** — it requires a manual
CSV export from the Anthropic console, then one command to ingest it.

This is not a limitation you can work around easily: Anthropic's programmatic Usage API
is gated to Organization-tier accounts. Team/Pro subscribers get CSV exports only.

---

## When to do this

Once a month is enough for trend analysis. The CIPHER n8n pipeline runs mostly
cached Haiku calls; the numbers don't change fast. Do it when you want to refresh the
"API Actual" section of the BurnRate dashboard.

---

## Step 1 — Export from Anthropic Console

1. Open [console.anthropic.com](https://console.anthropic.com) and log in with the
   ZeroNonsense.dev API account (the one that holds the `cipher-n8n` key).

2. Go to **Settings → Usage** (left sidebar).

3. In the date filter, pick the range you want. For a monthly refresh, set it to the
   previous calendar month.  
   > Export in chunks no larger than ~90 days if you have high volume — Anthropic
   > sometimes silently truncates very large date ranges.

4. Click **Export CSV**.  
   The file downloads as something like `usage_2026-04-01_2026-05-19.csv`.

5. Rename it to something descriptive before moving it:
   ```
   api_usage_cipher_2026-05.csv
   ```
   Naming doesn't matter to the importer, but it helps you keep track later.

---

## Step 2 — Drop the CSV into BurnRate

Copy the file into:
```
BurnRate\db\api_usage\
```

Full path:
```
C:\Users\WilcoDeTree\OneDrive - Valona Intelligence\Claude Cowork Output\BurnRate\db\api_usage\api_usage_cipher_2026-05.csv
```

The importer reads **all** `.csv` files in that folder and deduplicates by
`(date, api_key, model)`, so it is safe to drop overlapping exports — re-running
on the same CSV twice produces the same output.

---

## Step 3 — Run the import

Open a terminal, `cd` into the BurnRate folder, and run:

```powershell
cd "C:\Users\WilcoDeTree\OneDrive - Valona Intelligence\Claude Cowork Output\BurnRate"
python src\api_import.py
```

Expected output:
```
[OK] Parsed 312 CSV rows from db/api_usage
[OK] Wrote 53 daily records to api_daily.json
[OK] Wrote summary to api_summary.json

Date range:    2026-04-01 to 2026-05-19  (49 days)
Models seen:   claude-haiku-4-5-20251001, claude-haiku-4-5
API keys:      cipher-n8n
Projects:      cipher

Grand totals over 49 days:
  input (no cache):            142,311  full price
  cache writes (5m+1h):        823,441  ~1.25x base
  cache reads:               8,260,122  ~0.10x base price (BIG SAVINGS)
  output:                      504,811
  TOTAL INPUT:               9,225,874
  TOTAL BILLED:              9,730,685
  cache_read_share:              89.5%  of input came from cache hits
```

The two files it writes:

| File | What it contains |
|---|---|
| `db/api_daily.json` | One row per `(date, api_key, project, model)` with all token fields |
| `db/api_summary.json` | Grand totals, date range, cache share percentage |

---

## Step 4 — Refresh the dashboard

After importing, re-run the `render` command to embed the fresh data into the dashboard:

```powershell
python src\cowork_estimator.py render
```

Then open `dashboard\dashboard.html` in your browser.  
Go to the **API Actual** section — it should now show the updated date range and
cache share stat.

---

## Adding a new API key (e.g. JARVIS or DSI)

When a new project starts making API calls, its key will appear in the export CSV.
Open `src/api_import.py` and add a mapping in `API_KEY_TO_PROJECT`:

```python
API_KEY_TO_PROJECT = {
    "cipher-n8n":   "cipher",    # already present
    "jarvis-cloud": "jarvis",    # add when jarvis key is live
    "datastream":   "dsi",       # add when DSI key is live
    "burnrate-proxy": "burnrate", # add in Phase 2
}
```

The value is the project slug used everywhere in BurnRate (`cipher`, `jarvis`, `dsi`,
`gha`, `burnrate`, `hub`, `other`). Unknown keys default to `"other"`.

---

## What the CSV columns mean

The Anthropic console CSV has these token columns:

| Column | What it is | Price tier |
|---|---|---|
| `usage_input_tokens_no_cache` | Fresh input — not in any cache | Full price |
| `usage_input_tokens_cache_write_5m` | Tokens written to a 5-min ephemeral cache | ~1.25× base |
| `usage_input_tokens_cache_write_1h` | Tokens written to a 1-hour ephemeral cache | ~1.25× base |
| `usage_input_tokens_cache_read` | Tokens served from cache | ~0.10× base (10× cheaper) |
| `usage_output_tokens` | Completion tokens generated | ~3× input price |

**Effective input** = sum of all four input columns.  
**Cache read share** = `cache_read / effective_input` — the number to watch.
CIPHER is currently at ~86–90%. That means roughly 90% of the apparent input cost
is actually billed at one-tenth the rate.

---

## Things that can go wrong

**"No CSVs in db/api_usage"**  
You either put the file in the wrong folder or it isn't a `.csv` file.
Check the extension (Excel sometimes saves as `.xlsx` if you open and re-save it —
don't do that, use the raw download).

**Numbers look lower than expected**  
Check whether the export date range covers what you intended. The Anthropic console
date filter is UTC — a run at 23:00 Amsterdam time may land on the next UTC day.

**Dashboard shows stale numbers after import**  
You forgot to run `python src\cowork_estimator.py render`. The dashboard reads from
the embedded `window.BURNRATE_DATA` block, which is only updated by `render`.

**A new model name appears you don't recognise**  
Anthropic occasionally renames model versions. The importer stores the raw
`model_version` string from the CSV — nothing breaks, it just shows up as a new
row in the model list. No action needed.

---

## Quick reference

```powershell
# Full monthly refresh — one-liner
cd "C:\Users\WilcoDeTree\OneDrive - Valona Intelligence\Claude Cowork Output\BurnRate"
python src\api_import.py && python src\cowork_estimator.py render
```

That's it. Export, drop, two commands, done.
