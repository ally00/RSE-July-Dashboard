# Rwanda Stock Exchange — Trading Dashboard

A dark-themed, tabbed, interactive Streamlit dashboard for RSE trading activity —
built to load a new month's data with zero code changes.

## What's new in this version

- **Dark theme** (green-dominant, RSE-inspired) via `.streamlit/config.toml` +
  matching custom CSS — no white backgrounds anywhere.
- **Tabbed navigation**, not a long scroll: Overview & KPIs, Trends, Comparisons,
  Distributions, Variations & Correlations, Concentration, Alerts, Data Explorer,
  Ethics & Insights.
- **Corrected security classification.** `BOK`, `BLR`, `MTNR`, `IMR`, and `CMR` are
  real RSE-listed **equities** (Bank of Kigali, Bralirwa, MTN Rwandacell, I&M Bank
  Rwanda, CIMERWA) — not money-market instruments as an earlier version guessed.
  `FXD...` and `BSLB...` codes are classified as **Bonds**. This split now matches
  the Bond/Equity filter and the "Securities by Type" chart.
- **Upload next month's data right in the sidebar** — no rebuilding, no code
  edits. Drop in a `.csv` or `.xlsx` file with the same columns (Posting Date,
  Buyer Code, Seller Code, Security, Quantity, Price, Turnover, Deals) and every
  KPI, chart, insight, and alert regenerates automatically. The header, period
  label ("August 2026", etc.), and all analysis are derived from whatever data
  is loaded — nothing is hard-coded to a specific month.
- **Safer data-quality handling.** Broker codes that don't match the standard
  `BR<digits>` pattern are **flagged for manual review** (with possible matches
  shown) rather than silently auto-corrected. Testing showed fuzzy string
  matching on short codes can confidently pick the *wrong* correction (e.g.
  `BR1O` matching `BR1` instead of the more likely `BR10`) — for financial trade
  data, a wrong silent "fix" is worse than asking a human to confirm.

## Files

- `app.py` — the dashboard. The current dataset is embedded directly in the file
  (zero external file dependencies — see below), so it can't fail with a
  "file not found" error on any hosting platform.
- `.streamlit/config.toml` — forces the dark theme for native Streamlit widgets
  (sidebar, selects, tabs, buttons), not just the custom-styled elements.
- `data/rse_trades_clean.csv` — the current cleaned trade log, included for
  reference/download. Optional: if present next to `app.py`, the app prefers it
  over the embedded copy — handy for swapping in a new month without touching
  the code at all, as an alternative to the in-app uploader.
- `requirements.txt` — Python dependencies.

## How to load a new month's data

You have two options, both with zero rebuilding:

1. **In the running app (recommended):** open the sidebar → "📤 Upload trading
   data" → drop in the new month's `.csv` or `.xlsx`. The whole dashboard
   updates immediately, and the source is used only for that session.
2. **Replace the shipped file:** overwrite `data/rse_trades_clean.csv` with the
   new month's cleaned export and redeploy — the app will use it automatically
   in place of the embedded dataset.

Either way, the file just needs these columns: `Posting Date`, `Buyer Code`,
`Seller Code`, `Security`, `Quantity`, `Price`, `Turnover`, `Deals`.

## How to run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## How to deploy on Streamlit Community Cloud

1. Push `app.py`, `.streamlit/config.toml`, and `requirements.txt` to a GitHub
   repo (the `data/` folder is optional).
2. On [share.streamlit.io](https://share.streamlit.io), create a new app with
   **Main file path** set to `app.py`.
3. Deploy. Because the dataset is embedded, there's no external file for the
   deploy to lose track of.
