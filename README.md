# Rwanda Stock Exchange — July 2026 Trading Dashboard

An interactive Streamlit dashboard analyzing RSE bond/securities trading activity for July 2026.

## Files

- `app.py` — the Streamlit dashboard application
- `data/rse_july_2026_clean.csv` — cleaned trade log (source: Sheet1 of `July_2026.xlsx`)
- `requirements.txt` — Python dependencies

## Data cleaning applied

- Trimmed trailing/leading whitespace from security names (e.g. `FXD3/13.250%/2039/20YRS ` → `FXD3/13.250%/2039/20YRS`), which had been silently splitting some securities into duplicate categories.
- Corrected a seller-code typo: `B10` → `BR10`.
- Classified each security into a type: Government Bond (FXD), Treasury Bond (BOK), Government Bond (BSLB), or Money Market Instrument (IMR/BLR/MTNR/CMR).
- The dashboard's own `load_data()` function re-applies this cleaning defensively and reports exactly what it changed in the **Ethics & Data Quality** section.

## How to run

1. Install dependencies (Python 3.10+ recommended):
   ```bash
   pip install -r requirements.txt
   ```
2. From this folder, launch the app:
   ```bash
   streamlit run app.py
   ```
3. Streamlit will open the dashboard in your browser (default: http://localhost:8501).

## Notes

- All figures are computed dynamically from the underlying data — nothing is hard-coded.
- Filters (date range/day, security, security type, broker) are in the sidebar and update every section live.
- If a filter combination returns no data, the dashboard shows a friendly message rather than crashing.
