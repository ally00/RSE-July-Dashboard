"""
Rwanda Stock Exchange (RSE) — July 2026 Trading Dashboard
Run with:  streamlit run app.py
"""

from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ----------------------------------------------------------------------------
# PAGE CONFIG
# ----------------------------------------------------------------------------
st.set_page_config(
    page_title="RSE — July 2026 Trading Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ----------------------------------------------------------------------------
# COLORS (RSE-inspired: green primary, dark blue secondary, gold accent)
# ----------------------------------------------------------------------------
GREEN_DARK = "#0B4D2C"
GREEN = "#1E7B45"
GREEN_LIGHT = "#E4F3E8"
BLUE_DARK = "#0B2545"
BLUE = "#134074"
GOLD = "#C9971C"
GOLD_LIGHT = "#FCF3DA"
RED = "#B3261E"
RED_LIGHT = "#FBE7E6"
TEXT_DARK = "#1A1A1A"
BG = "#F7F9F7"

CHART_COLORWAY = [GREEN, BLUE, GOLD, GREEN_DARK, BLUE_DARK, "#6FA985", "#8FA6C7"]

st.markdown(
    f"""
    <style>
    .stApp {{ background-color: {BG}; }}
    h1, h2, h3 {{ color: {GREEN_DARK}; }}
    .kpi-card {{
        border-radius: 12px;
        padding: 16px 18px;
        color: white;
        margin-bottom: 8px;
    }}
    .kpi-value {{ font-size: 26px; font-weight: 700; margin: 0; }}
    .kpi-label {{ font-size: 13px; font-weight: 500; opacity: 0.9; margin: 0; }}
    .kpi-exact {{ font-size: 11px; opacity: 0.75; margin-top: 4px; }}
    .alert-box {{
        border-radius: 10px;
        padding: 12px 16px;
        margin-bottom: 10px;
        font-size: 14px;
        font-weight: 500;
    }}
    .section-note {{
        background-color: {GREEN_LIGHT};
        color: {GREEN_DARK};
        padding: 10px 14px;
        border-radius: 8px;
        font-size: 14px;
        margin-bottom: 12px;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

PLOTLY_TEMPLATE = dict(
    layout=dict(
        colorway=CHART_COLORWAY,
        font=dict(color=TEXT_DARK, size=13),
        title_font=dict(color=GREEN_DARK, size=16),
        paper_bgcolor="white",
        plot_bgcolor="white",
        legend=dict(font=dict(color=TEXT_DARK)),
        xaxis=dict(title_font=dict(color=TEXT_DARK), tickfont=dict(color=TEXT_DARK), gridcolor="#E5E5E5"),
        yaxis=dict(title_font=dict(color=TEXT_DARK), tickfont=dict(color=TEXT_DARK), gridcolor="#E5E5E5"),
    )
)

# ----------------------------------------------------------------------------
# DATA LOADING & CLEANING
# ----------------------------------------------------------------------------
# Resolve the data path relative to this script's own location, not the
# process's current working directory — Streamlit Cloud does not always
# launch with the repo root as the working directory.
APP_DIR = Path(__file__).resolve().parent
DATA_PATH = APP_DIR / "data" / "rse_july_2026_clean.csv"


@st.cache_data
def load_data(path: str):
    """Load, validate, and clean the RSE trade log. Returns df + quality report."""
    df = pd.read_csv(path)
    quality = {"trimmed_security_names": 0, "seller_code_fixes": 0, "duplicates_removed": 0,
               "missing_before": {}, "invalid_rows_dropped": 0}

    df["Posting Date"] = pd.to_datetime(df["Posting Date"], errors="coerce")

    for col in ["Posting Date", "Buyer Code", "Seller Code", "Security", "Quantity", "Price", "Turnover", "Deals"]:
        if col in df.columns:
            quality["missing_before"][col] = int(df[col].isna().sum())

    for col in ["Security", "Buyer Code", "Seller Code"]:
        before = df[col].copy()
        df[col] = df[col].astype(str).str.strip()
        if col == "Security":
            quality["trimmed_security_names"] = int((before != df[col]).sum())

    fixes = int((df["Seller Code"] == "B10").sum())
    df["Seller Code"] = df["Seller Code"].replace({"B10": "BR10"})
    quality["seller_code_fixes"] = fixes

    for col in ["Quantity", "Price", "Turnover", "Deals"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    before_rows = len(df)
    df = df.dropna(subset=["Posting Date", "Security", "Quantity", "Price", "Turnover", "Deals"])
    quality["invalid_rows_dropped"] = before_rows - len(df)

    before_rows = len(df)
    df = df.drop_duplicates()
    quality["duplicates_removed"] = before_rows - len(df)

    def classify(sec: str) -> str:
        if sec.startswith("FXD"):
            return "Government Bond (FXD)"
        if sec == "BOK":
            return "Treasury Bond (BOK)"
        if sec.startswith("BSLB"):
            return "Government Bond (BSLB)"
        if sec in ["IMR", "BLR", "MTNR", "CMR"]:
            return "Money Market Instrument"
        return "Other"

    df["Security Type"] = df["Security"].apply(classify)
    df["Trading Date"] = df["Posting Date"].dt.date
    df = df.sort_values("Posting Date").reset_index(drop=True)

    return df, quality


try:
    df_raw, quality_report = load_data(str(DATA_PATH))
except FileNotFoundError:
    st.error(
        f"Could not find the dataset at `{DATA_PATH}`.\n\n"
        "If you're seeing this on Streamlit Community Cloud, double-check that:\n"
        "1. `data/rse_july_2026_clean.csv` was actually committed and pushed to GitHub "
        "(run `git status` / check the file appears in the GitHub repo UI — empty or "
        ".gitignore'd `data/` folders are a common culprit).\n"
        "2. The file path/casing matches exactly (`data/rse_july_2026_clean.csv`, "
        "all lowercase) — Streamlit Cloud runs on Linux, which is case-sensitive.\n"
        "3. The app's 'Main file path' in Streamlit Cloud settings points to `app.py` "
        "at the repo root, so this relative `data/` folder resolves correctly."
    )
    st.stop()

if df_raw.empty:
    st.error("The dataset loaded but contains no usable trade records after cleaning.")
    st.stop()

MIN_DATE = df_raw["Posting Date"].min().date()
MAX_DATE = df_raw["Posting Date"].max().date()

# ----------------------------------------------------------------------------
# FORMATTING HELPERS
# ----------------------------------------------------------------------------
def fmt_rwf(value: float) -> str:
    if pd.isna(value):
        return "RWF 0"
    if abs(value) >= 1e9:
        return f"RWF {value / 1e9:.2f}B"
    if abs(value) >= 1e6:
        return f"RWF {value / 1e6:.1f}M"
    if abs(value) >= 1e3:
        return f"RWF {value / 1e3:.1f}K"
    return f"RWF {value:,.0f}"


def fmt_qty(value: float) -> str:
    if pd.isna(value):
        return "0"
    if abs(value) >= 1e6:
        return f"{value / 1e6:.2f}M"
    if abs(value) >= 1e3:
        return f"{value / 1e3:.1f}K"
    return f"{value:,.0f}"


def fmt_exact_rwf(value: float) -> str:
    return f"RWF {value:,.0f}" if not pd.isna(value) else "RWF 0"


def fmt_date(d) -> str:
    return pd.to_datetime(d).strftime("%d %b %Y")


def fmt_pct(value: float) -> str:
    if pd.isna(value) or np.isinf(value):
        return "n/a"
    return f"{value:+.1f}%"


def kpi_card(label, value_display, exact_display, bg=GREEN_DARK):
    st.markdown(
        f"""
        <div class="kpi-card" style="background-color:{bg};" title="{exact_display}">
            <p class="kpi-label">{label}</p>
            <p class="kpi-value">{value_display}</p>
            <p class="kpi-exact">Exact: {exact_display}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def alert_box(message, level="info"):
    colors = {
        "green": (GREEN_LIGHT, GREEN_DARK),
        "gold": (GOLD_LIGHT, "#7A5A00"),
        "red": (RED_LIGHT, RED),
        "info": ("#E7EEF7", BLUE_DARK),
    }
    bg, fg = colors.get(level, colors["info"])
    st.markdown(
        f'<div class="alert-box" style="background-color:{bg}; color:{fg};">{message}</div>',
        unsafe_allow_html=True,
    )


def safe_corr(x: pd.Series, y: pd.Series):
    """Returns (r, n) or (None, n) if correlation cannot be computed."""
    paired = pd.concat([x, y], axis=1).dropna()
    n = len(paired)
    if n < 3 or paired.iloc[:, 0].std() == 0 or paired.iloc[:, 1].std() == 0:
        return None, n
    r = paired.iloc[:, 0].corr(paired.iloc[:, 1])
    return r, n


# ----------------------------------------------------------------------------
# SIDEBAR — NAVIGATION & FILTERS
# ----------------------------------------------------------------------------
st.sidebar.markdown("## 📊 RSE Dashboard")
st.sidebar.markdown("**Analysis Period:** July 2026")
st.sidebar.markdown("---")

st.sidebar.markdown("### 🗓️ Trading Day Navigation")
view_mode = st.sidebar.radio(
    "View",
    ["Full Month View", "Select Date Range", "Single Trading Day"],
    index=0,
)

trading_days_sorted = sorted(df_raw["Trading Date"].unique())

if view_mode == "Full Month View":
    date_start, date_end = MIN_DATE, MAX_DATE
elif view_mode == "Select Date Range":
    date_range = st.sidebar.date_input(
        "Date range", value=(MIN_DATE, MAX_DATE), min_value=MIN_DATE, max_value=MAX_DATE
    )
    if isinstance(date_range, tuple) and len(date_range) == 2:
        date_start, date_end = date_range
    else:
        date_start, date_end = MIN_DATE, MAX_DATE
else:
    selected_day = st.sidebar.selectbox(
        "Select Trading Day",
        options=trading_days_sorted,
        index=len(trading_days_sorted) - 1,
        format_func=fmt_date,
    )
    date_start = date_end = selected_day
    st.sidebar.info(f"Showing: **{fmt_date(selected_day)}**")

st.sidebar.markdown("---")
st.sidebar.markdown("### 🔎 Filters")

security_options = sorted(df_raw["Security"].unique())
selected_securities = st.sidebar.multiselect("Security", security_options, default=[])

type_options = sorted(df_raw["Security Type"].unique())
selected_types = st.sidebar.multiselect("Security Type", type_options, default=[])

broker_options = sorted(set(df_raw["Buyer Code"]) | set(df_raw["Seller Code"]))
selected_brokers = st.sidebar.multiselect("Broker (Buyer or Seller)", broker_options, default=[])

if st.sidebar.button("🔄 Reset Filters"):
    st.rerun()

mask = (df_raw["Trading Date"] >= date_start) & (df_raw["Trading Date"] <= date_end)
if selected_securities:
    mask &= df_raw["Security"].isin(selected_securities)
if selected_types:
    mask &= df_raw["Security Type"].isin(selected_types)
if selected_brokers:
    mask &= df_raw["Buyer Code"].isin(selected_brokers) | df_raw["Seller Code"].isin(selected_brokers)

df = df_raw.loc[mask].copy()

st.sidebar.markdown("---")
st.sidebar.caption(f"Showing **{len(df):,}** of {len(df_raw):,} trade records.")

# ----------------------------------------------------------------------------
# HEADER
# ----------------------------------------------------------------------------
st.markdown("# Rwanda Stock Exchange — July 2026 Trading Dashboard")
st.markdown(
    """
The **Rwanda Stock Exchange (RSE)** is the national securities exchange of Rwanda, providing a
regulated marketplace for buying, selling, and listing financial instruments such as shares,
corporate bonds, and government securities. It is an organized and regulated financial market
where securities are bought and sold at prices governed by the forces of demand and supply.
"""
)
st.markdown(
    """
**Dataset:** This dashboard analyzes RSE trading activity during **July 2026**, focusing on
turnover, trading volume, number of deals, securities traded, daily market movements,
variations, relationships between variables, and other indicators of market activity.
"""
)
st.markdown(f"**Analysis Period: July 2026**  |  Currently viewing: **{fmt_date(date_start)} – {fmt_date(date_end)}**")
st.markdown("---")

if df.empty:
    st.warning("Not enough data is available for this analysis under the selected filters.")
    st.stop()

# ----------------------------------------------------------------------------
# MARKET OVERVIEW — KPIs
# ----------------------------------------------------------------------------
st.markdown("## 📌 Market Overview")

daily = df.groupby("Trading Date").agg(
    Turnover=("Turnover", "sum"),
    Volume=("Quantity", "sum"),
    Deals=("Deals", "sum"),
).reset_index()
daily = daily.sort_values("Trading Date").reset_index(drop=True)
daily["Avg Deal Size"] = daily["Turnover"] / daily["Deals"].replace(0, np.nan)

total_turnover = df["Turnover"].sum()
total_volume = df["Quantity"].sum()
total_deals = df["Deals"].sum()
n_securities = df["Security"].nunique()
n_days = daily["Trading Date"].nunique()
avg_daily_turnover = daily["Turnover"].mean()
avg_daily_volume = daily["Volume"].mean()
avg_deal_size = total_turnover / total_deals if total_deals else np.nan
max_turnover_row = daily.loc[daily["Turnover"].idxmax()]
max_volume_row = daily.loc[daily["Volume"].idxmax()]
max_deals_row = daily.loc[daily["Deals"].idxmax()]

k1, k2, k3, k4 = st.columns(4)
with k1:
    kpi_card("Total Turnover", fmt_rwf(total_turnover), fmt_exact_rwf(total_turnover), GREEN_DARK)
with k2:
    kpi_card("Total Trading Volume", f"{fmt_qty(total_volume)} shares/units", f"{total_volume:,.0f}", BLUE_DARK)
with k3:
    kpi_card("Number of Deals", f"{total_deals:,}", f"{total_deals:,}", GREEN)
with k4:
    kpi_card("Securities Traded", f"{n_securities}", f"{n_securities}", BLUE)

k5, k6, k7, k8 = st.columns(4)
with k5:
    kpi_card("Avg Daily Turnover", fmt_rwf(avg_daily_turnover), fmt_exact_rwf(avg_daily_turnover), GREEN_DARK)
with k6:
    kpi_card("Avg Daily Volume", fmt_qty(avg_daily_volume), f"{avg_daily_volume:,.0f}", BLUE_DARK)
with k7:
    kpi_card("Avg Deal Size", fmt_rwf(avg_deal_size), fmt_exact_rwf(avg_deal_size), GREEN)
with k8:
    kpi_card("Active Trading Days", f"{n_days}", f"{n_days}", BLUE)

k9, k10, k11 = st.columns(3)
with k9:
    kpi_card("Highest Daily Turnover", fmt_rwf(max_turnover_row["Turnover"]),
              f'{fmt_exact_rwf(max_turnover_row["Turnover"])} on {fmt_date(max_turnover_row["Trading Date"])}', GOLD)
with k10:
    kpi_card("Highest Daily Volume", fmt_qty(max_volume_row["Volume"]),
              f'{max_volume_row["Volume"]:,.0f} on {fmt_date(max_volume_row["Trading Date"])}', GOLD)
with k11:
    kpi_card("Highest Number of Deals", f'{int(max_deals_row["Deals"])}',
              f'{int(max_deals_row["Deals"])} on {fmt_date(max_deals_row["Trading Date"])}', GOLD)

st.markdown("### Summary")
sec_turnover = df.groupby("Security")["Turnover"].sum().sort_values(ascending=False)
sec_volume = df.groupby("Security")["Quantity"].sum().sort_values(ascending=False)
sec_deals = df.groupby("Security")["Deals"].sum().sort_values(ascending=False)
top_turnover_sec = sec_turnover.index[0]
top_volume_sec = sec_volume.index[0]
top_deals_sec = sec_deals.index[0]

min_turnover_row = daily.loc[daily["Turnover"].idxmin()]

st.markdown(
    f"""
- **Strongest trading day:** {fmt_date(max_turnover_row['Trading Date'])} recorded the highest turnover
  ({fmt_rwf(max_turnover_row['Turnover'])}), indicating unusually strong market activity.
- **Weakest trading day:** {fmt_date(min_turnover_row['Trading Date'])} recorded the lowest turnover
  ({fmt_rwf(min_turnover_row['Turnover'])}) among active trading days.
- **Highest-volume day:** {fmt_date(max_volume_row['Trading Date'])} with {fmt_qty(max_volume_row['Volume'])} units traded.
- **Most active by deals:** {fmt_date(max_deals_row['Trading Date'])} with {int(max_deals_row['Deals'])} deals recorded.
- **Highest-turnover security:** **{top_turnover_sec}** contributed {fmt_rwf(sec_turnover.iloc[0])}.
- **Highest-volume security:** **{top_volume_sec}** with {fmt_qty(sec_volume.iloc[0])} units traded.
- **Most active security (by deals):** **{top_deals_sec}** with {int(sec_deals.iloc[0])} deals.
"""
)

st.markdown("---")

# ----------------------------------------------------------------------------
# TRENDS
# ----------------------------------------------------------------------------
st.markdown("## 📈 Trends")
st.markdown(
    '<div class="section-note">All charts below show every available trading day in July 2026, in '
    'chronological order. Hover for exact values; use the toolbar to zoom, pan, or reset the view.</div>',
    unsafe_allow_html=True,
)

fig_turnover = go.Figure()
fig_turnover.add_trace(go.Scatter(
    x=daily["Trading Date"], y=daily["Turnover"], mode="lines+markers",
    line=dict(color=GREEN, width=3), marker=dict(size=6),
    customdata=daily["Turnover"],
    hovertemplate="<b>%{x|%d %b %Y}</b><br>Turnover: RWF %{customdata:,.0f}<extra></extra>",
    name="Daily Turnover",
))
fig_turnover.update_layout(
    **PLOTLY_TEMPLATE["layout"], title="Daily Turnover Trend (RWF)",
    xaxis_title="Trading Date", yaxis_title="Turnover (RWF)",
    yaxis_tickformat=".2s", height=420,
)
st.plotly_chart(fig_turnover, use_container_width=True)

fig_volume = go.Figure()
fig_volume.add_trace(go.Scatter(
    x=daily["Trading Date"], y=daily["Volume"], mode="lines+markers",
    line=dict(color=BLUE, width=3), marker=dict(size=6),
    customdata=daily["Volume"],
    hovertemplate="<b>%{x|%d %b %Y}</b><br>Volume: %{customdata:,.0f}<extra></extra>",
    name="Daily Volume",
))
fig_volume.update_layout(
    **PLOTLY_TEMPLATE["layout"], title="Daily Trading Volume",
    xaxis_title="Trading Date", yaxis_title="Volume (units)",
    yaxis_tickformat=".2s", height=420,
)
st.plotly_chart(fig_volume, use_container_width=True)
st.caption("Higher trading volume indicates that more shares or securities were exchanged during the trading day.")

fig_deals = go.Figure()
fig_deals.add_trace(go.Scatter(
    x=daily["Trading Date"], y=daily["Deals"], mode="lines+markers",
    line=dict(color=GOLD, width=3), marker=dict(size=6),
    hovertemplate="<b>%{x|%d %b %Y}</b><br>Deals: %{y:,}<extra></extra>",
    name="Daily Deals",
))
fig_deals.update_layout(
    **PLOTLY_TEMPLATE["layout"], title="Number of Deals by Trading Day",
    xaxis_title="Trading Date", yaxis_title="Number of Deals", height=380,
)
st.plotly_chart(fig_deals, use_container_width=True)

fig_ads = go.Figure()
fig_ads.add_trace(go.Scatter(
    x=daily["Trading Date"], y=daily["Avg Deal Size"], mode="lines+markers",
    line=dict(color=BLUE_DARK, width=3), marker=dict(size=6),
    hovertemplate="<b>%{x|%d %b %Y}</b><br>Avg Deal Size: RWF %{y:,.0f}<extra></extra>",
    name="Avg Deal Size",
))
fig_ads.update_layout(
    **PLOTLY_TEMPLATE["layout"], title="Average Deal Size Trend (Turnover ÷ Deals)",
    xaxis_title="Trading Date", yaxis_title="Avg Deal Size (RWF)",
    yaxis_tickformat=".2s", height=380,
)
st.plotly_chart(fig_ads, use_container_width=True)
st.caption(
    "Average deal size shows the typical value of a transaction. A higher value may indicate that "
    "larger transactions were contributing more to turnover. Days with zero deals are excluded."
)

st.markdown("### 🔥 Market Activity Heatmap")
heat_metric = st.selectbox("Activity measure", ["Turnover", "Volume", "Deals"], key="heatmap_metric")
heat_df = daily.copy()
heat_df["Trading Date"] = pd.to_datetime(heat_df["Trading Date"])
heat_df["Week"] = heat_df["Trading Date"].dt.isocalendar().week
heat_df["Weekday"] = heat_df["Trading Date"].dt.day_name()
weekday_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
pivot = heat_df.pivot_table(index="Weekday", columns="Week", values=heat_metric, aggfunc="sum")
pivot = pivot.reindex(weekday_order).dropna(how="all")
if pivot.empty:
    st.info("Not enough data is available for this analysis under the selected filters.")
else:
    fig_heat = px.imshow(
        pivot, color_continuous_scale=[[0, "#EAF5EE"], [0.5, GREEN], [1, GREEN_DARK]],
        aspect="auto", labels=dict(color=heat_metric),
    )
    fig_heat.update_layout(**PLOTLY_TEMPLATE["layout"], title=f"Daily {heat_metric} Heatmap (by Week / Weekday)", height=350)
    st.plotly_chart(fig_heat, use_container_width=True)

st.markdown("### 🧾 Daily Market Summary Table")
table_df = daily.copy()
table_df["Trading Date"] = pd.to_datetime(table_df["Trading Date"]).dt.strftime("%d %b %Y")
table_df = table_df.rename(columns={"Volume": "Volume (units)"})
st.dataframe(
    table_df.style.format({
        "Turnover": "RWF {:,.0f}", "Volume (units)": "{:,.0f}",
        "Deals": "{:,.0f}", "Avg Deal Size": "RWF {:,.0f}",
    }).highlight_max(subset=["Turnover", "Volume (units)", "Deals"], color=GREEN_LIGHT)
      .highlight_min(subset=["Turnover", "Volume (units)", "Deals"], color=RED_LIGHT),
    use_container_width=True, height=320,
)
st.download_button(
    "⬇️ Download Daily Summary (CSV)",
    data=table_df.to_csv(index=False).encode("utf-8"),
    file_name="rse_daily_summary_july2026.csv",
    mime="text/csv",
)

st.markdown("---")

# ----------------------------------------------------------------------------
# COMPARISONS
# ----------------------------------------------------------------------------
st.markdown("## 🏆 Comparisons")
top_n = st.radio("Show top:", [5, 10, 15], index=1, horizontal=True)

c1, c2, c3 = st.columns(3)

with c1:
    top_t = sec_turnover.head(top_n).sort_values()
    fig = px.bar(top_t, x=top_t.values, y=top_t.index, orientation="h",
                 labels={"x": "Turnover (RWF)", "y": "Security"}, text=top_t.values)
    fig.update_traces(marker_color=GREEN, texttemplate="RWF %{text:.2s}", textposition="outside",
                       hovertemplate="<b>%{y}</b><br>Turnover: RWF %{x:,.0f}<extra></extra>")
    fig.update_layout(**PLOTLY_TEMPLATE["layout"], title=f"Top {top_n} Securities by Turnover", height=420)
    st.plotly_chart(fig, use_container_width=True)

with c2:
    top_v = sec_volume.head(top_n).sort_values()
    fig = px.bar(top_v, x=top_v.values, y=top_v.index, orientation="h",
                 labels={"x": "Volume", "y": "Security"}, text=top_v.values)
    fig.update_traces(marker_color=BLUE, texttemplate="%{text:.2s}", textposition="outside",
                       hovertemplate="<b>%{y}</b><br>Volume: %{x:,.0f}<extra></extra>")
    fig.update_layout(**PLOTLY_TEMPLATE["layout"], title=f"Top {top_n} Securities by Volume", height=420)
    st.plotly_chart(fig, use_container_width=True)

with c3:
    top_d = sec_deals.head(top_n).sort_values()
    fig = px.bar(top_d, x=top_d.values, y=top_d.index, orientation="h",
                 labels={"x": "Deals", "y": "Security"}, text=top_d.values)
    fig.update_traces(marker_color=GOLD, texttemplate="%{text}", textposition="outside",
                       hovertemplate="<b>%{y}</b><br>Deals: %{x}<extra></extra>")
    fig.update_layout(**PLOTLY_TEMPLATE["layout"], title=f"Top {top_n} Securities by Deals", height=420)
    st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

# ----------------------------------------------------------------------------
# VARIATIONS
# ----------------------------------------------------------------------------
st.markdown("## 🔀 Variations")
var_df = daily.copy()
for col in ["Turnover", "Volume", "Deals"]:
    var_df[f"{col} Abs Change"] = var_df[col].diff()
    var_df[f"{col} % Change"] = var_df[col].pct_change() * 100

st.markdown(
    """
- **Absolute Change** = Current value − Previous value
- **Percentage Change** = ((Current − Previous) / Previous) × 100
"""
)

var_metric = st.selectbox("Select metric for variation chart", ["Turnover", "Volume", "Deals"], key="var_metric")
if len(var_df) < 2:
    st.info("Not enough data is available for this analysis under the selected filters.")
else:
    colors = np.where(var_df[f"{var_metric} % Change"].fillna(0) >= 0, GREEN, RED)
    fig_var = go.Figure()
    fig_var.add_trace(go.Bar(
        x=pd.to_datetime(var_df["Trading Date"]), y=var_df[f"{var_metric} % Change"],
        marker_color=colors,
        customdata=np.stack([var_df[var_metric], var_df[var_metric].shift(1), var_df[f"{var_metric} Abs Change"]], axis=-1),
        hovertemplate=(
            "<b>%{x|%d %b %Y}</b><br>Current: %{customdata[0]:,.0f}<br>Previous: %{customdata[1]:,.0f}"
            "<br>Absolute Change: %{customdata[2]:,.0f}<br>%% Change: %{y:.1f}%<extra></extra>"
        ),
    ))
    fig_var.add_hline(y=0, line_color=TEXT_DARK, line_width=1)
    fig_var.update_layout(**PLOTLY_TEMPLATE["layout"], title=f"Daily {var_metric} % Change",
                           xaxis_title="Trading Date", yaxis_title="% Change", height=400)
    st.plotly_chart(fig_var, use_container_width=True)

    vcol1, vcol2, vcol3 = st.columns(3)
    std_val = daily[var_metric].std()
    mean_val = daily[var_metric].mean()
    cv = (std_val / mean_val * 100) if mean_val else np.nan
    with vcol1:
        kpi_card(f"{var_metric} Std. Deviation", fmt_rwf(std_val) if var_metric != "Deals" else f"{std_val:,.1f}",
                  f"{std_val:,.2f}", BLUE_DARK)
    with vcol2:
        kpi_card(f"{var_metric} Coefficient of Variation", f"{cv:.1f}%" if pd.notna(cv) else "n/a",
                  f"{cv:.2f}%" if pd.notna(cv) else "n/a", GREEN_DARK)
    with vcol3:
        max_abs_move = var_df[f"{var_metric} % Change"].abs().max()
        kpi_card(f"Largest {var_metric} Swing", fmt_pct(max_abs_move) if pd.notna(max_abs_move) else "n/a",
                  fmt_pct(max_abs_move) if pd.notna(max_abs_move) else "n/a", GOLD)

    st.caption("Coefficient of variation (std. deviation ÷ mean) expresses volatility relative to the average level, "
               "making it easier to compare variability across metrics of different scale.")

st.markdown("---")

# ----------------------------------------------------------------------------
# CORRELATIONS & RELATIONSHIPS
# ----------------------------------------------------------------------------
st.markdown("## 🔗 Correlations & Relationships")

corr_cols = ["Turnover", "Volume", "Deals", "Avg Deal Size"]
corr_data = daily[corr_cols]
if len(corr_data.dropna()) >= 3:
    corr_matrix = corr_data.corr(numeric_only=True)
    fig_corr = px.imshow(
        corr_matrix, text_auto=".2f", color_continuous_scale=[[0, RED], [0.5, "#FFFFFF"], [1, GREEN_DARK]],
        zmin=-1, zmax=1, aspect="auto",
    )
    fig_corr.update_layout(**PLOTLY_TEMPLATE["layout"], title="Correlation Heatmap (Daily Aggregates)", height=420)
    st.plotly_chart(fig_corr, use_container_width=True)
else:
    alert_box("Not enough data is available for this analysis under the selected filters.", "gold")

pairs = [("Turnover", "Volume"), ("Turnover", "Deals"), ("Volume", "Deals")]
for x_col, y_col in pairs:
    r, n = safe_corr(daily[x_col], daily[y_col])
    scol1, scol2 = st.columns([2, 1])
    with scol1:
        try:
            fig_sc = px.scatter(
                daily, x=x_col, y=y_col, trendline="ols" if r is not None else None,
                hover_data={"Trading Date": True},
                color_discrete_sequence=[GREEN],
            )
        except Exception:
            fig_sc = px.scatter(daily, x=x_col, y=y_col, hover_data={"Trading Date": True},
                                 color_discrete_sequence=[GREEN])
        fig_sc.update_traces(marker=dict(size=9, color=GREEN, line=dict(width=1, color=GREEN_DARK)),
                              selector=dict(mode="markers"))
        fig_sc.update_layout(**PLOTLY_TEMPLATE["layout"], title=f"{x_col} vs {y_col}", height=360)
        st.plotly_chart(fig_sc, use_container_width=True)
    with scol2:
        if r is None:
            st.info("Not enough data is available for this analysis under the selected filters.")
        else:
            strength = "strong" if abs(r) >= 0.7 else "moderate" if abs(r) >= 0.4 else "weak"
            direction = "positive" if r >= 0 else "negative"
            st.metric(f"Correlation ({x_col} vs {y_col})", f"{r:.2f}")
            st.caption(f"Observations: {n}")
            st.write(
                f"A correlation of {r:.2f} indicates a {strength} {direction} relationship. "
                f"In this dataset, days with higher {x_col.lower()} generally tended to have "
                f"{'higher' if r >= 0 else 'lower'} {y_col.lower()}."
            )
st.markdown("**Correlation does not prove causation.**")

st.markdown("---")

# ----------------------------------------------------------------------------
# DISTRIBUTIONS
# ----------------------------------------------------------------------------
st.markdown("## 📊 Distributions")

dcol1, dcol2, dcol3 = st.columns(3)
with dcol1:
    fig = px.histogram(daily, x="Turnover", nbins=min(10, max(1, len(daily))), color_discrete_sequence=[GREEN])
    fig.update_layout(**PLOTLY_TEMPLATE["layout"], title="Daily Turnover Distribution", height=350)
    st.plotly_chart(fig, use_container_width=True)
with dcol2:
    fig = px.histogram(daily, x="Volume", nbins=min(10, max(1, len(daily))), color_discrete_sequence=[BLUE])
    fig.update_layout(**PLOTLY_TEMPLATE["layout"], title="Trading Volume Distribution", height=350)
    st.plotly_chart(fig, use_container_width=True)
with dcol3:
    fig = px.histogram(daily, x="Deals", nbins=min(10, max(1, len(daily))), color_discrete_sequence=[GOLD])
    fig.update_layout(**PLOTLY_TEMPLATE["layout"], title="Number of Deals Distribution", height=350)
    st.plotly_chart(fig, use_container_width=True)

st.markdown(
    f"""
- **Typical turnover:** median day traded around {fmt_rwf(daily['Turnover'].median())}, with a spread
  (std. deviation) of {fmt_rwf(daily['Turnover'].std())}.
- **Typical volume:** median day saw {fmt_qty(daily['Volume'].median())} units traded.
- **Typical deal count:** median day recorded {daily['Deals'].median():.0f} deals.
"""
)

st.markdown("### 🚨 Outlier Analysis")


def find_outliers_iqr(series: pd.Series, dates: pd.Series, label: str):
    if len(series.dropna()) < 4:
        return []
    q1, q3 = series.quantile(0.25), series.quantile(0.75)
    iqr = q3 - q1
    lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    flagged = []
    for d, v in zip(dates, series):
        if pd.isna(v):
            continue
        if v < lower or v > upper:
            reason = f"Below lower bound ({lower:,.0f})" if v < lower else f"Above upper bound ({upper:,.0f})"
            flagged.append({"Date": fmt_date(d), "Metric": label, "Value": v, "Reason": reason})
    return flagged


outlier_rows = []
outlier_rows += find_outliers_iqr(daily["Turnover"], daily["Trading Date"], "Turnover")
outlier_rows += find_outliers_iqr(daily["Volume"], daily["Trading Date"], "Volume")
outlier_rows += find_outliers_iqr(daily["Deals"], daily["Trading Date"], "Deals")

if outlier_rows:
    out_df = pd.DataFrame(outlier_rows)
    st.dataframe(out_df, use_container_width=True)
    st.caption("An outlier is a value that is unusually high or low compared with the normal pattern "
               "(identified here using the IQR method: values beyond 1.5× the interquartile range).")
else:
    st.info("No statistically significant outliers were detected in daily Turnover, Volume, or Deals for the selected period.")

st.markdown("---")

# ----------------------------------------------------------------------------
# MARKET CONCENTRATION
# ----------------------------------------------------------------------------
st.markdown("## 🎯 Market Concentration")
conc = (sec_turnover / sec_turnover.sum() * 100).sort_values(ascending=False)
top_conc = conc.head(10).sort_values()
fig_conc = px.bar(top_conc, x=top_conc.values, y=top_conc.index, orientation="h",
                   text=top_conc.values, labels={"x": "% of Total Turnover", "y": "Security"})
fig_conc.update_traces(marker_color=GREEN_DARK, texttemplate="%{text:.1f}%", textposition="outside",
                        hovertemplate="<b>%{y}</b><br>Share of Turnover: %{x:.1f}%<extra></extra>")
fig_conc.update_layout(**PLOTLY_TEMPLATE["layout"], title="Turnover Contribution by Security (Top 10)", height=420)
st.plotly_chart(fig_conc, use_container_width=True)

top3_share = conc.head(3).sum()
st.markdown(f"**{conc.index[0]}** contributed **{conc.iloc[0]:.1f}%** of total turnover during the selected period. "
            f"The top 3 securities together accounted for **{top3_share:.1f}%** of total turnover, "
            f"{'indicating a concentrated market' if top3_share > 60 else 'indicating activity is fairly distributed across securities'}.")

st.markdown("---")

# ----------------------------------------------------------------------------
# ALERTS
# ----------------------------------------------------------------------------
st.markdown("## 🔔 Market Alerts")

alert_box(
    f"📈 <b>Highest Turnover Day:</b> {fmt_date(max_turnover_row['Trading Date'])} — {fmt_rwf(max_turnover_row['Turnover'])}",
    "green",
)
alert_box(
    f"📉 <b>Lowest Turnover Day:</b> {fmt_date(min_turnover_row['Trading Date'])} — {fmt_rwf(min_turnover_row['Turnover'])}",
    "info",
)
alert_box(
    f"🔊 <b>Highest Volume Day:</b> {fmt_date(max_volume_row['Trading Date'])} — {fmt_qty(max_volume_row['Volume'])} units",
    "green",
)
alert_box(
    f"🤝 <b>Highest Deal Count:</b> {fmt_date(max_deals_row['Trading Date'])} — {int(max_deals_row['Deals'])} deals",
    "info",
)

if len(var_df) >= 2:
    max_swing = var_df["Turnover % Change"].abs().max()
    if pd.notna(max_swing) and max_swing > 100:
        swing_row = var_df.loc[var_df["Turnover % Change"].abs().idxmax()]
        alert_box(
            f"⚠️ <b>Large Turnover Variation:</b> {fmt_date(swing_row['Trading Date'])} saw a "
            f"{fmt_pct(swing_row['Turnover % Change'])} change vs the previous trading day.",
            "gold" if max_swing < 300 else "red",
        )

if top3_share > 70:
    alert_box(
        f"⚠️ <b>High Market Concentration:</b> Top 3 securities account for {top3_share:.1f}% of turnover — "
        f"activity is concentrated in a small number of instruments.",
        "gold",
    )

if outlier_rows:
    alert_box(f"🔍 <b>Outliers Detected:</b> {len(outlier_rows)} daily observation(s) flagged as statistical outliers "
              f"— see the Distributions section for details.", "gold")

if quality_report["seller_code_fixes"] or quality_report["invalid_rows_dropped"] or quality_report["duplicates_removed"]:
    alert_box(
        f"ℹ️ <b>Data Quality Note:</b> {quality_report['seller_code_fixes']} seller-code correction(s), "
        f"{quality_report['duplicates_removed']} duplicate row(s), and {quality_report['invalid_rows_dropped']} "
        f"invalid row(s) were cleaned automatically. See Ethics &amp; Data Quality for details.",
        "info",
    )

st.markdown("---")

# ----------------------------------------------------------------------------
# KEY INSIGHTS
# ----------------------------------------------------------------------------
st.markdown("## 💡 Key Insights")

turnover_trend = "increased" if daily["Turnover"].iloc[-1] > daily["Turnover"].iloc[0] else "decreased"
vol_turnover_r, _ = safe_corr(daily["Volume"], daily["Turnover"])
deals_turnover_r, _ = safe_corr(daily["Deals"], daily["Turnover"])

st.markdown(
    f"""
> **Market Activity:** Trading activity fluctuated throughout the selected period, with the highest
> turnover recorded on {fmt_date(max_turnover_row['Trading Date'])} and the lowest on
> {fmt_date(min_turnover_row['Trading Date'])}.

> **Market Concentration:** **{conc.index[0]}** alone accounted for {conc.iloc[0]:.1f}% of total turnover,
> and the top 3 securities together made up {top3_share:.1f}% — {'a notably concentrated' if top3_share > 60 else 'a moderately distributed'} pattern of activity.

> **Trading Volume:** {"Higher-volume days were generally associated with higher turnover" if vol_turnover_r and vol_turnover_r > 0.4 else "Volume and turnover did not show a strong consistent relationship"} 
> (correlation: {f"{vol_turnover_r:.2f}" if vol_turnover_r is not None else "n/a"}).

> **Deal Activity:** {"More transactions tended to coincide with higher turnover" if deals_turnover_r and deals_turnover_r > 0.4 else "The number of deals did not strongly track turnover"} 
> (correlation: {f"{deals_turnover_r:.2f}" if deals_turnover_r is not None else "n/a"}).

> **Outliers:** {"Statistical outliers were detected in daily activity — see the Distributions section for the specific dates and metrics." if outlier_rows else "No significant statistical outliers were found in daily Turnover, Volume, or Deals."}

> **Overall Direction:** Turnover across the selected period {turnover_trend} from
> {fmt_rwf(daily['Turnover'].iloc[0])} on {fmt_date(daily['Trading Date'].iloc[0])} to
> {fmt_rwf(daily['Turnover'].iloc[-1])} on {fmt_date(daily['Trading Date'].iloc[-1])}.
"""
)

st.markdown("---")

# ----------------------------------------------------------------------------
# RECOMMENDATIONS
# ----------------------------------------------------------------------------
st.markdown("## 📋 Recommendations")
st.markdown(
    f"""
- **Market Monitoring:** Continue tracking daily turnover and deal activity around
  {fmt_date(max_turnover_row['Trading Date'])}-type peaks to understand what drives unusually strong trading days.
- **Liquidity:** With **{top_deals_sec}** and **{top_volume_sec}** among the most actively traded instruments,
  monitor whether liquidity is sufficiently broad-based across the full security list.
- **Market Concentration:** Given that the top 3 securities represent {top3_share:.1f}% of turnover, consider
  whether measures to encourage trading in a wider range of securities would be beneficial.
- **Unusual Activity:** Investigate the flagged outlier trading days to confirm whether they reflect genuine
  market events, large institutional trades, or data-entry issues.
- **Data Quality:** Continue enforcing consistent formatting of security codes and broker codes at the point
  of data entry to reduce the need for downstream cleaning.
- **Investor Analysis:** Use the Data Explorer and broker filters to examine which brokers are driving
  turnover on peak trading days.
"""
)

st.markdown("---")

# ----------------------------------------------------------------------------
# DATA EXPLORER
# ----------------------------------------------------------------------------
st.markdown("## 🗂️ Data Explorer")

ecol1, ecol2, ecol3, ecol4 = st.columns(4)
ecol1.metric("Rows", f"{len(df):,}")
ecol2.metric("Columns", f"{df.shape[1]}")
ecol3.metric("Date Range", f"{fmt_date(date_start)} – {fmt_date(date_end)}")
ecol4.metric("Missing Values", f"{int(df.isna().sum().sum())}")

available_cols = list(df.columns)
selected_cols = st.multiselect("Select columns to display", available_cols, default=available_cols)
search_term = st.text_input("Search (matches Security, Buyer Code, or Seller Code)")

explorer_df = df[selected_cols].copy() if selected_cols else df.copy()
if search_term:
    text_cols = [c for c in ["Security", "Buyer Code", "Seller Code"] if c in explorer_df.columns]
    if text_cols:
        cond = np.zeros(len(explorer_df), dtype=bool)
        for c in text_cols:
            cond |= explorer_df[c].astype(str).str.contains(search_term, case=False, na=False)
        explorer_df = explorer_df[cond]

st.dataframe(explorer_df, use_container_width=True, height=350)
st.download_button(
    "⬇️ Download Filtered Data (CSV)",
    data=explorer_df.to_csv(index=False).encode("utf-8"),
    file_name="rse_july2026_filtered.csv",
    mime="text/csv",
)

st.markdown("---")

# ----------------------------------------------------------------------------
# ETHICS & DATA QUALITY
# ----------------------------------------------------------------------------
st.markdown("## ⚖️ Ethics & Data Quality")

st.markdown("### Data Quality Report")
qcol1, qcol2, qcol3 = st.columns(3)
qcol1.metric("Seller-code corrections (B10 → BR10)", quality_report["seller_code_fixes"])
qcol2.metric("Duplicate rows removed", quality_report["duplicates_removed"])
qcol3.metric("Invalid rows dropped", quality_report["invalid_rows_dropped"])

missing_summary = {k: v for k, v in quality_report["missing_before"].items() if v}
if missing_summary:
    st.write("Missing values found before cleaning:", missing_summary)
else:
    st.write("No missing values were found in the source data prior to cleaning.")

st.markdown(
    """
### Ethics
- Data is presented accurately, based only on the records contained in the July 2026 trade log.
- No results have been manipulated, smoothed, or selectively excluded.
- Confidential or personally identifying information is not exposed — broker codes only, no individual identities.
- **Correlation does not prove causation** — relationships shown are observational, not causal.
- Flagged outliers require further investigation before being treated as errors or genuine market events.
- Insights on this dashboard are intended to support, not replace, professional analytical judgment.
"""
)

st.markdown("---")

# ----------------------------------------------------------------------------
# GLOSSARY
# ----------------------------------------------------------------------------
st.markdown("## 📖 Glossary")

glossary = {
    "RSE": "The Rwanda Stock Exchange — Rwanda's national, regulated securities market.",
    "Turnover": "The total monetary value of securities traded (Quantity × Price).",
    "Trading Volume": "The total number of shares or units of a security that changed hands.",
    "Number of Deals": "The count of individual transactions executed.",
    "Deal": "A single completed transaction between a buyer and a seller.",
    "Average Deal Size": "Total turnover divided by the number of deals — the typical value per transaction.",
    "Liquidity": "How easily a security can be bought or sold without significantly affecting its price.",
    "Market Activity": "A general term for how much trading (turnover, volume, deals) occurred in a period.",
    "Variation": "A change in a metric from one period to another, shown as an absolute or percentage change.",
    "Percentage Change": "((Current − Previous) / Previous) × 100.",
    "Volatility": "The degree of variation in a metric over time, often measured using standard deviation.",
    "Correlation": "A statistical measure (from -1 to +1) of how two variables move together.",
    "Positive Correlation": "When two variables tend to increase or decrease together.",
    "Negative Correlation": "When one variable tends to increase as the other decreases.",
    "Outlier": "A value that is unusually high or low compared with the normal pattern of the data.",
    "Market Concentration": "The degree to which trading activity is dominated by a small number of securities.",
    "Security": "A tradable financial instrument, such as a bond or share.",
    "Share": "A unit of ownership in a company.",
    "Corporate Bond": "A debt instrument issued by a company, paying periodic interest.",
    "Government Security": "A debt instrument issued by the government (e.g. Treasury bonds, FXD bonds).",
    "Trading Day": "A calendar day on which the market is open and trades were recorded.",
    "Demand": "The willingness and ability of buyers to purchase a security at a given price.",
    "Supply": "The quantity of a security that sellers are willing to offer at a given price.",
}

gcol1, gcol2 = st.columns(2)
items = list(glossary.items())
half = len(items) // 2 + len(items) % 2
for term, definition in items[:half]:
    gcol1.markdown(f"**{term}:** {definition}")
for term, definition in items[half:]:
    gcol2.markdown(f"**{term}:** {definition}")

st.markdown("### Dashboard Colors")
st.markdown(
    """
- **Green:** Main RSE-inspired dashboard color — used for primary trends and positive indicators.
- **Dark Blue:** Secondary professional color — used for supporting charts and navigation.
- **Yellow/Gold:** Supporting accent color — used for warnings and highlights.
"""
)

st.markdown("---")
st.caption("Rwanda Stock Exchange — July 2026 Trading Dashboard · Built with Streamlit & Plotly")
