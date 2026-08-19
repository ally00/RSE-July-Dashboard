# Rwanda Stock Exchange — July 2026 Trading Dashboard

An interactive Streamlit dashboard analyzing RSE bond/securities trading activity for July 2026.

## Files

- `app.py` — the Streamlit dashboard application. **The July 2026 dataset is embedded
  directly inside this file**, so it has zero external file dependencies and cannot
  fail with a "file not found" error on any hosting platform.
- `data/rse_july_2026_clean.csv` — the same cleaned trade log as a standalone CSV,
  included for reference/download. It is *optional*: if present next to `app.py`,
  the app will use it instead of the embedded copy (handy for swapping in a new
  month's data without editing the script). If it's absent — which is fine, and is
  the expected state after a normal GitHub push where only `app.py` matters — the
  app silently falls back to its embedded data.
- `requirements.txt` — Python dependencies

## Why the data is embedded

The previous version of this app read `data/rse_july_2026_clean.csv` from disk at
startup, which repeatedly failed on Streamlit Community Cloud with
`Could not find the dataset at /mount/src/.../data/rse_july_2026_clean.csv` —
even after confirming the path logic itself was correct. That class of error
(repo layout mismatches, `.gitignore` rules, stale deploy caches, "Main file path"
misconfiguration) is eliminated entirely by not depending on a separate file at
all. You can still upload a replacement CSV at runtime via the "📤 Data source"
expander in the sidebar if you want to point the dashboard at a different month.

## Data cleaning applied

- Trimmed trailing/leading whitespace from security names (e.g. `FXD3/13.250%/2039/20YRS ` → `FXD3/13.250%/2039/20YRS`), which had been silently splitting some securities into duplicate categories.
- Corrected a seller-code typo: `B10` → `BR10`.
- Classified each security into a type: Government Bond (FXD), Treasury Bond (BOK), Government Bond (BSLB), or Money Market Instrument (IMR/BLR/MTNR/CMR).
- The dashboard's own `load_data()` function re-applies this cleaning defensively and reports exactly what it changed in the **Ethics & Data Quality** section.

## How to run locally

1. Install dependencies (Python 3.10+ recommended):
   ```bash
   pip install -r requirements.txt
   ```
2. From this folder, launch the app:
   ```bash
   streamlit run app.py
   ```
3. Streamlit will open the dashboard in your browser (default: http://localhost:8501).

## How to deploy on Streamlit Community Cloud

1. Push this folder's contents to a GitHub repo. At minimum you need `app.py` and
   `requirements.txt` at the repo root — `data/` is optional now.
2. On [share.streamlit.io](https://share.streamlit.io), create a new app pointing at
   your repo, with **Main file path** set to `app.py`.
3. Deploy. Because the dataset is embedded, there is no `data/` folder for the
   "Main file path" or repo layout to get wrong — if `app.py` is found, the
   dashboard will load with data.

## Notes

- All figures are computed dynamically from the underlying data — nothing is hard-coded.
- Filters (date range/day, security, security type, broker) are in the sidebar and update every section live.
- If a filter combination returns no data, the dashboard shows a friendly message rather than crashing.
