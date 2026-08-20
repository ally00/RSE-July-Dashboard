"""
Rwanda Stock Exchange (RSE) — Trading Dashboard
Run with:  streamlit run app.py
"""

import difflib
import io
import re
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
    page_title="RSE Trading Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ----------------------------------------------------------------------------
# COLOR PALETTE — dark theme, green dominant (RSE-inspired)
# ----------------------------------------------------------------------------
BG = "#0E1117"            # main app background (near-black)
SIDEBAR_BG = "#161B22"    # sidebar / card background
CARD_BG = "#161B22"
BORDER = "#2A3038"

GREEN = "#1E8449"         # primary brand green
GREEN_DARK = "#14532D"
GREEN_BRIGHT = "#22A559"
GREEN_LIGHT_TEXT = "#8FE3B0"

BLUE = "#1B3A5C"          # secondary — used for Equity series
BLUE_LIGHT = "#3E6FA8"

GOLD = "#D4A017"          # accent — warnings/highlights
GOLD_LIGHT = "#3A2E10"

RED = "#C0392B"
RED_LIGHT = "#3A1414"

TEXT_LIGHT = "#F5F7FA"
TEXT_MUTED = "#9AA4B2"

CHART_COLORWAY = [GREEN_BRIGHT, BLUE_LIGHT, GOLD, "#6FCF97", "#8FA6C7", "#E0B84A", "#4C9F70"]

st.markdown(
    f"""
    <style>
    .stApp {{ background-color: {BG}; color: {TEXT_LIGHT}; }}
    section[data-testid="stSidebar"] {{ background-color: {SIDEBAR_BG}; }}
    h1, h2, h3, h4 {{ color: {TEXT_LIGHT}; }}
    p, span, label, div {{ color: {TEXT_LIGHT}; }}
    .stTabs [data-baseweb="tab-list"] {{
        gap: 4px;
        border-bottom: 1px solid {BORDER};
    }}
    .stTabs [data-baseweb="tab"] {{
        background-color: transparent;
        color: {TEXT_MUTED};
        border-radius: 6px 6px 0 0;
        padding: 8px 14px;
    }}
    .stTabs [aria-selected="true"] {{
        color: {GREEN_BRIGHT} !important;
        border-bottom: 2px solid {GREEN_BRIGHT};
        font-weight: 600;
    }}
    .kpi-card {{
        border-radius: 10px;
        padding: 16px 18px;
        color: white;
        margin-bottom: 10px;
        border: 1px solid rgba(255,255,255,0.06);
    }}
    .kpi-label {{
        font-size: 12px; font-weight: 700; letter-spacing: 0.06em;
        text-transform: uppercase; opacity: 0.85; margin: 0 0 6px 0;
    }}
    .kpi-unit {{ font-size: 13px; font-weight: 600; opacity: 0.9; margin: 0; }}
    .kpi-value {{ font-size: 26px; font-weight: 800; margin: 0; line-height: 1.15; }}
    .kpi-exact {{ font-size: 11px; opacity: 0.7; margin-top: 6px; }}
    .quote-box {{
        background-color: {GREEN_DARK};
        border-left: 5px solid {GOLD};
        border-radius: 8px;
        padding: 20px 26px;
        margin: 14px 0 18px 0;
    }}
    .quote-mark {{ color: {GOLD}; font-size: 28px; font-weight: 800; line-height: 0.5; }}
    .quote-text {{ color: {TEXT_LIGHT}; font-size: 15.5px; font-style: italic; line-height: 1.55; }}
    .quote-attrib {{ color: {GREEN_LIGHT_TEXT}; font-size: 13px; text-align: right; margin-top: 10px; }}
    .alert-box {{
        border-radius: 8px; padding: 12px 16px; margin-bottom: 10px;
        font-size: 14px; font-weight: 500; border: 1px solid rgba(255,255,255,0.05);
    }}
    .section-note {{
        background-color: rgba(30,132,73,0.15);
        color: {GREEN_LIGHT_TEXT};
        padding: 10px 14px; border-radius: 8px; font-size: 13.5px; margin-bottom: 12px;
        border: 1px solid rgba(30,132,73,0.3);
    }}
    .meta-line {{ color: {TEXT_MUTED}; font-size: 13.5px; }}
    [data-testid="stDataFrame"] {{ background-color: {CARD_BG}; }}
    </style>
    """,
    unsafe_allow_html=True,
)

PLOTLY_LAYOUT = dict(
    colorway=CHART_COLORWAY,
    font=dict(color=TEXT_LIGHT, size=13),
    title_font=dict(color=TEXT_LIGHT, size=16),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    legend=dict(font=dict(color=TEXT_LIGHT)),
    xaxis=dict(title_font=dict(color=TEXT_MUTED), tickfont=dict(color=TEXT_MUTED), gridcolor=BORDER, zerolinecolor=BORDER),
    yaxis=dict(title_font=dict(color=TEXT_MUTED), tickfont=dict(color=TEXT_MUTED), gridcolor=BORDER, zerolinecolor=BORDER),
)

# ----------------------------------------------------------------------------
# KNOWN RSE-LISTED EQUITIES
# ----------------------------------------------------------------------------
# The Rwanda Stock Exchange has 10 listed equities. Any security code matching
# one of these tickers is classified as an Equity Security; codes matching a
# bond-style naming pattern (e.g. FXD.../rate%/year/tenor) are classified as
# Debt Securities. This generalizes correctly to future months without
# hard-coding a specific dataset.
KNOWN_EQUITIES = {
    "BOK": "Bank of Kigali Group PLC",
    "BLR": "Bralirwa PLC",
    "MTNR": "MTN Rwandacell PLC",
    "IMR": "I&M Bank Rwanda PLC",
    "CMR": "CIMERWA PLC",
    "EQTY": "Equity Group Holdings PLC",
    "KCB": "KCB Group PLC",
    "NMG": "Nation Media Group PLC",
    "RHB": "RH Bophelo PLC",
    "USL": "Uchumi Supermarkets PLC",
}

BOND_PATTERN = re.compile(r"\d+(\.\d+)?%.*\d{4}", re.IGNORECASE)


def classify_security(sec: str) -> str:
    """Classify a security code as Equity, Bond, or Other. Uses the known
    RSE equity ticker list first, then falls back to a generic bond-naming
    pattern (rate% / maturity year), so new tickers/bond series in future
    months are still classified sensibly without code changes."""
    sec = str(sec).strip().upper()
    if sec in KNOWN_EQUITIES:
        return "Equity"
    if sec.startswith("FXD") or sec.startswith("BSLB") or sec.startswith("BOK-") or BOND_PATTERN.search(sec):
        return "Bond"
    if sec in {"BOK", "IMR", "BLR", "MTNR", "CMR"}:  # safety net for the known tickers even if casing/format drifts
        return "Equity"
    # generic fallback: short alphabetic codes without bond-style punctuation look like equity tickers
    if re.fullmatch(r"[A-Z]{2,6}", sec):
        return "Equity"
    return "Bond"


def security_display_name(sec: str) -> str:
    company = KNOWN_EQUITIES.get(str(sec).strip().upper())
    return f"{sec} — {company}" if company else sec
EMBEDDED_CSV = """Posting Date,Buyer Code,Seller Code,Security,Quantity,Price,Turnover,Deals
2026-07-02,BR10,BR9,MTNR,2000,130.0,260000.0,1
2026-07-02,BR10,BR10,FXD6/13.15%/2045/20YRS,13900000,1.035,14386499.999999998,1
2026-07-02,BR10,BR10,FXD4/13.000%/2041/20YRS,7600000,1.04,7904000.0,1
2026-07-02,BR10,BR10,FXD1/13.290%/2043/20YRS,27200000,1.045,28424000.0,1
2026-07-02,BR3,BR3,FXD1/13.290%/2043/20YRS,200000,1.08081,216162.0,1
2026-07-02,BR10,BR10,FXD3/13.250%/2039/20YRS,15000000,1.04,15600000.0,1
2026-07-02,BR10,BR10,FXD6/13.15%/2040/20YRS,15000000,1.05,15750000.0,1
2026-07-02,BR3,BR3,FXD8/13.270%/2044/20YRS,6500000,1.026,6669000.0,1
2026-07-02,BR10,BR10,FXD8/13.270%/2044/20YRS,3000000,1.002,3006000.0,1
2026-07-02,BR3,BR10,BLR,400,490.0,196000.0,1
2026-07-02,BR2,BR10,BLR,1600,490.0,784000.0,1
2026-07-02,BR10,BR10,BLR,6800,490.0,3332000.0,1
2026-07-02,BR10,BR10,IMR,200,90.0,18000.0,1
2026-07-02,BR10,BR9,IMR,5400,90.0,486000.0,1
2026-07-02,BR9,BR9,BOK,11200,600.0,6720000.0,1
2026-07-02,BR9,BR10,BLR,1300,490.0,637000.0,1
2026-07-03,BR10,BR10,BLR,4700,490.0,2303000.0,1
2026-07-03,BR9,BR9,FXD2/12.550%/2035/15YRS,10000000,1.05,10500000.0,1
2026-07-03,BR3,BR3,FXD8/13.270%/2044/20YRS,9200000,1.0035,9232200.0,1
2026-07-03,BR9,BR9,IMR,5000,90.0,450000.0,1
2026-07-03,BR9,BR9,FXD8/13.270%/2044/20YRS,5000000,1.006,5030000.0,1
2026-07-03,BR9,BR9,BOK,157700,600.0,94620000.0,1
2026-07-03,BR10,BR10,BOK,6100,600.0,3660000.0,1
2026-07-03,BR10,BR9,IMR,1000,90.0,90000.0,1
2026-07-03,BR9,BR9,MTNR,2900,130.0,377000.0,1
2026-07-07,BR4,BR4,FXD6/13.15%/2045/20YRS,168000000,1.04,174720000.0,1
2026-07-07,BR9,BR9,FXD8/13.270%/2044/20YRS,10000000,1.01,10100000.0,1
2026-07-07,BR3,BR3,FXD8/13.270%/2044/20YRS,8500000,1.028,8738000.0,1
2026-07-07,BR10,BR10,BLR,300,490.0,147000.0,1
2026-07-07,BR10,BR10,FXD6/13.15%/2045/20YRS,48400000,1.045,50578000.0,1
2026-07-07,BR2,BR9,IMR,4800,90.0,432000.0,1
2026-07-07,BR9,BR9,IMR,6500,90.0,585000.0,1
2026-07-07,BR10,BR10,IMR,3000,90.0,270000.0,1
2026-07-07,BR10,BR10,BOK,500,600.0,300000.0,1
2026-07-07,BR3,BR3,IMR,2000,90.0,180000.0,1
2026-07-08,BR10,BR10,FXD1/12.00%/2036/10YRS,10000000,1.055,10550000.0,1
2026-07-08,BR9,BR9,FXD5/11.750%/2029/7YRS,405000000,1.04,421200000.0,1
2026-07-08,BR9,BR9,FXD2/12.550%/2035/15YRS,10000000,1.052,10520000.0,1
2026-07-08,BR10,BR10,FXD3/13.250%/2039/20YRS,10000000,1.055,10550000.0,1
2026-07-08,BR9,BR9,FXD8/13.270%/2044/20YRS,8500000,1.01,8585000.0,1
2026-07-08,BR9,BR9,IMR,200,90.0,18000.0,1
2026-07-08,BR9,BR9,MTNR,3000,130.0,390000.0,1
2026-07-08,BR10,BR10,FXD8/13.270%/2044/20YRS,4000000,1.01,4040000.0,1
2026-07-09,BR9,BR9,BLR,200,490.0,98000.0,1
2026-07-09,BR3,BR3,FXD2/11.00%/2030/5YRS,1000000,1.005,1005000.0,1
2026-07-09,BR9,BR9,FXD5/11.750%/2029/7YRS,500000000,1.041,520500000.0,1
2026-07-09,BR3,BR3,FXD3/11.50%/2032/7YRS,576500000,1.07559,620077635.0,1
2026-07-09,BR10,BR10,BLR,4000,490.0,1960000.0,1
2026-07-09,BR3,BR9,MTNR,1000,130.0,130000.0,1
2026-07-09,BR4,BR4,BOK,500,600.0,300000.0,1
2026-07-09,BR1,BR9,MTNR,6000,130.0,780000.0,1
2026-07-09,BR10,BR10,IMR,2000,90.0,180000.0,1
2026-07-09,BR2,BR9,MTNR,2300,130.0,299000.0,1
2026-07-10,BR10,BR10,FXD6/13.15%/2040/20YRS,500000,1.05,525000.0,1
2026-07-10,BR10,BR10,BLR,1000,490.0,490000.0,1
2026-07-10,BR9,BR9,FXD8/13.270%/2044/20YRS,25000000,1.01,25250000.0,1
2026-07-10,BR2,BR10,BOK,5000,600.0,3000000.0,1
2026-07-10,BR10,BR10,BOK,2000,600.0,1200000.0,1
2026-07-10,BR10,BR10,IMR,2500,90.0,225000.0,1
2026-07-13,BR10,BR10,FXD6/13.15%/2040/20YRS,800000,1.05,840000.0,1
2026-07-13,BR10,BR10,FXD3/12.983%/2034/10YRS,200000,1.01,202000.0,1
2026-07-13,BR10,BR10,FXD4/13.000%/2041/20YRS,100000,1.03,103000.0,1
2026-07-13,BR10,BR10,FXD6/13.15%/2045/20YRS,200000,1.01,202000.0,1
2026-07-14,BR10,BR3,BLR,2300,490.0,1127000.0,1
2026-07-14,BR4,BR9,FXD5/13.00%/2040/15YRS,516200000,1.052,543042400.0,1
2026-07-14,BR10,BR10,FXD6/13.15%/2045/20YRS,60600000,1.045,63326999.99999999,1
2026-07-14,BR9,BR9,BOK,17400,600.0,10440000.0,1
2026-07-14,BR3,BR3,FXD3/11.50%/2032/7YRS,500000000,1.07437,537185000.0,1
2026-07-14,BR9,BR10,BOK,4800,600.0,2880000.0,1
2026-07-14,BR10,BR10,BOK,1000,600.0,600000.0,1
2026-07-14,BR10,BR3,MTNR,3000,130.0,390000.0,1
2026-07-14,BR4,BR10,BOK,1200,600.0,720000.0,1
2026-07-15,BR2,BR10,BOK,500,600.0,300000.0,1
2026-07-15,BR10,BR10,IMR,11500,90.0,1035000.0,1
2026-07-15,BR10,BR10,FXD3/13.250%/2039/20YRS,1000000,1.052,1052000.0,1
2026-07-15,BR3,BR3,FXD4/13.000%/2041/20YRS,10800000,1.044,11275200.0,1
2026-07-16,BR3,BR3,FXD6/13.15%/2045/20YRS,300000000,1.0535,316050000.00000006,1
2026-07-16,BR4,BR4,BLR,700,495.0,346500.0,1
2026-07-16,BR10,BR10,BLR,3500,490.0,1715000.0,1
2026-07-16,BR10,BR10,IMR,2400,90.0,216000.0,1
2026-07-16,BR9,BR3,MTNR,18000,130.0,2340000.0,1
2026-07-16,BR9,BR9,MTNR,4000,130.0,520000.0,1
2026-07-17,BR9,BR9,CMR,2600,160.0,416000.0,1
2026-07-17,BR9,BR9,FXD6/13.15%/2045/20YRS,15000000,1.033,15494999.999999998,1
2026-07-17,BR3,BR3,FXD4/13.000%/2041/20YRS,10000000,1.045,10450000.0,1
2026-07-17,BR4,BR4,FXD1/13.150%/2042/20YRS,10000000,1.0,10000000.0,1
2026-07-17,BR10,BR10,FXD1/13.290%/2043/20YRS,20000000,1.01,20200000.0,1
2026-07-17,BR10,BR10,FXD1/13.290%/2043/20YRS,600000,1.005,602999.9999999999,1
2026-07-17,BR10,BR10,FXD3/13.250%/2039/20YRS,15000000,1.05,15750000.0,1
2026-07-17,BR3,BR3,BLR,6100,490.0,2989000.0,1
2026-07-17,BR2,BR2,BLR,4100,495.0,2029500.0,1
2026-07-17,BR1,BR2,IMR,100,90.0,9000.0,1
2026-07-17,BR4,BR2,IMR,4500,90.0,405000.0,1
2026-07-17,BR9,BR2,IMR,3800,90.0,342000.0,1
2026-07-17,BR2,BR2,IMR,6100,90.0,549000.0,1
2026-07-17,BR9,BR2,BOK,1600,600.0,960000.0,1
2026-07-17,BR9,BR9,MTNR,5300,130.0,689000.0,1
2026-07-17,BR9,BR3,MTNR,44000,130.0,5720000.0,1
2026-07-17,BR1,BR3,MTNR,6000,130.0,780000.0,1
2026-07-20,BR9,BR9,BOK,2200,600.0,1320000.0,1
2026-07-20,BR6,BR2,IMR,400,90.0,36000.0,1
2026-07-20,BR9,BR2,IMR,1400,90.0,126000.0,1
2026-07-20,BR9,BR9,BLR,6600,490.0,3234000.0,1
2026-07-20,BR2,BR9,BLR,3400,495.0,1683000.0,1
2026-07-20,BR3,BR3,FXD1/13.150%/2042/20YRS,7000000,1.001,7006999.999999999,1
2026-07-21,BR3,BR3,FXD1/13.150%/2042/20YRS,100000000,1.025,102500000.0,1
2026-07-21,BR10,BR10,FXD6/13.15%/2045/20YRS,442000000,1.02,450840000.0,1
2026-07-21,BR4,BR9,MTNR,800,132.0,105600.0,1
2026-07-21,BR9,BR9,BOK,23000,600.0,13800000.0,1
2026-07-22,BR4,BR4,FXD4/13.000%/2041/20YRS,7600000,1.05,7980000.0,1
2026-07-22,BR9,BR9,FXD3/11.50%/2032/7YRS,40000000,1.0085,40340000.0,1
2026-07-22,BR3,BR3,FXD1/13.290%/2043/20YRS,200000,1.005,201000.0,1
2026-07-22,BR9,BR9,FXD3/12.5%/2036/15YRS,20600000,1.03,21218000.0,1
2026-07-22,BR9,BR9,FXD3/12.9%/2033/15YRS,10000000,1.06,10600000.0,1
2026-07-22,BR2,BR2,BLR,200,495.0,99000.0,1
2026-07-22,BR9,BR2,IMR,4500,90.0,405000.0,1
2026-07-22,BR10,BR10,IMR,4200,90.0,378000.0,1
2026-07-22,BR10,BR10,BOK,6100,600.0,3660000.0,1
2026-07-22,BR1,BR10,MTNR,2800,130.0,364000.0,1
2026-07-22,BR6,BR10,MTNR,3200,130.0,416000.0,1
2026-07-22,BR10,BR10,MTNR,400,130.0,52000.0,1
2026-07-22,BR2,BR2,IMR,12900,90.0,1161000.0,1
2026-07-22,BR9,BR10,MTNR,17300,130.0,2249000.0,1
2026-07-23,BR4,BR10,BLR,500,495.0,247500.0,1
2026-07-23,BR3,BR3,FXD1/13.290%/2043/20YRS,300000,1.025,307500.0,1
2026-07-23,BR9,BR1,BLR,16600,500.0,8300000.0,1
2026-07-23,BR3,BR3,FXD2/11.00%/2030/5YRS,1000000,1.01,1010000.0,1
2026-07-23,BR9,BR9,FXD6/13.15%/2045/20YRS,9000000,1.035,9315000.0,1
2026-07-23,BR1,BR1,IMR,122700,90.0,11043000.0,1
2026-07-23,BR10,BR10,FXD6/13.15%/2045/20YRS,100000000,1.02,102000000.0,1
2026-07-23,BR10,BR10,IMR,1500,95.0,142500.0,1
2026-07-23,BR3,BR3,FXD1/12.150%/2035/10YRS,1000000,1.02,1020000.0,1
2026-07-23,BR10,BR2,IMR,1600,90.0,144000.0,1
2026-07-23,BR9,BR2,IMR,2100,90.0,189000.0,1
2026-07-23,BR4,BR9,BOK,1600,605.0,968000.0,1
2026-07-23,BR10,BR10,IMR,2400,90.0,216000.0,1
2026-07-23,BR4,BR9,BOK,400,600.0,240000.0,1
2026-07-23,BR9,BR9,BOK,105700,600.0,63420000.0,1
2026-07-23,BR9,BR10,BOK,700,600.0,420000.0,1
2026-07-23,BR9,BR10,MTNR,400,130.0,52000.0,1
2026-07-24,BR3,BR3,FXD2/11.50%/2033/7YRS,300000000,1.0195,305850000.0,1
2026-07-24,BR9,BR9,FXD1/13.290%/2043/20YRS,55000000,1.005,55274999.99999999,1
2026-07-24,BR10,BR10,FXD1/13.290%/2043/20YRS,500000,1.01,505000.0,1
2026-07-24,BR3,BR3,FXD3/12.5%/2036/15YRS,1500000,1.055,1582500.0,1
2026-07-24,BR10,BR10,IMR,7200,90.0,648000.0,1
2026-07-24,BR9,BR9,BLR,10000,500.0,5000000.0,1
2026-07-24,BR2,BR10,IMR,800,90.0,72000.0,1
2026-07-24,BR9,BR9,FXD8/13.270%/2044/20YRS,1800000,1.013,1823400.0,1
2026-07-27,BR3,BR3,BSLB/12.85%/2030/7YRS,6300000,1.055,6646500.0,1
2026-07-27,BR9,BR9,FXD6/13.15%/2045/20YRS,10000000,1.047,10470000.0,1
2026-07-27,BR3,BR3,FXD3/13.250%/2039/20YRS,2000000,1.059,2118000.0,1
2026-07-27,BR9,BR9,FXD6/13.15%/2045/20YRS,26000000,1.035,26910000.0,1
2026-07-27,BR6,BR9,BLR,6600,500.0,3300000.0,1
2026-07-27,BR9,BR9,IMR,1400,90.0,126000.0,1
2026-07-27,BR9,BR9,BOK,500,605.0,302500.0,1
2026-07-27,BR3,BR3,FXD8/13.270%/2044/20YRS,7500000,1.013,7597499.999999999,1
2026-07-28,BR9,BR9,MTNR,3000,130.0,390000.0,1
2026-07-28,BR1,BR1,BOK,18100,600.0,10860000.0,1
2026-07-28,BR2,BR9,IMR,1300,90.0,117000.0,1
2026-07-28,BR9,BR9,IMR,1100,90.0,99000.0,1
2026-07-28,BR10,BR10,IMR,10800,95.0,1026000.0,1
2026-07-28,BR9,BR9,FXD1/13.290%/2043/20YRS,15000000,1.005,15074999.999999998,1
2026-07-28,BR10,BR10,FXD1/13.290%/2043/20YRS,600000,1.012,607200.0,1
2026-07-28,BR3,BR3,FXD1/12.00%/2036/10YRS,6000000,1.0,6000000.0,1
2026-07-29,BR4,BR4,FXD1/13.150%/2042/20YRS,4000000,1.002,4008000.0,1
2026-07-29,BR10,BR10,IMR,9000,95.0,855000.0,1
2026-07-29,BR4,BR4,IMR,3700,90.0,333000.0,1
2026-07-29,BR9,BR9,MTNR,46700,135.0,6304500.0,1
2026-07-30,BR4,BR4,MTNR,1000,136.0,136000.0,1
2026-07-30,BR9,BR9,BOK,6300,600.0,3780000.0,1
2026-07-30,BR4,BR10,IMR,1700,90.0,153000.0,1
2026-07-30,BR9,BR9,IMR,500,90.0,45000.0,1
2026-07-30,BR10,BR10,IMR,8000,95.0,760000.0,1
2026-07-30,BR2,BR10,BLR,1500,500.0,750000.0,1
2026-07-30,BR10,BR10,FXD2/12.550%/2035/15YRS,52000000,1.04,54080000.0,1
2026-07-30,BR4,BR4,FXD1/13.150%/2042/20YRS,1000000,1.002,1002000.0,1
2026-07-30,BR10,BR10,FXD1/13.150%/2042/20YRS,100000,1.005,100500.0,1
2026-07-30,BR10,BR10,FXD6/13.15%/2045/20YRS,52400000,1.05,55020000.0,1
2026-07-31,BR9,BR9,FXD3/11.50%/2032/7YRS,10000000,1.0059,10059000.0,1
2026-07-31,BR9,BR9,FXD1/12.150%/2035/10YRS,1000000,1.0335,1033500.0,1
2026-07-31,BR9,BR9,FXD1/13.150%/2042/20YRS,7500000,1.0065,7548750.0,1
2026-07-31,BR4,BR4,BLR,1000000,500.0,500000000.0,1
2026-07-31,BR9,BR9,BLR,3000,500.0,1500000.0,1
2026-07-31,BR9,BR9,FXD5/13.00%/2040/15YRS,20000000,1.049,20980000.0,1
"""

REQUIRED_COLS = ["Posting Date", "Buyer Code", "Seller Code", "Security", "Quantity", "Price", "Turnover", "Deals"]


def _standardize_broker_codes(series: pd.Series) -> tuple[pd.Series, list]:
    """Uppercase/trim codes only. Deliberately does NOT auto-correct codes
    that look like typos: fuzzy string matching on short alphanumeric codes
    (e.g. 'BR1O' vs 'BR1' vs 'BR10') is unreliable and can confidently pick
    the wrong canonical code, which is worse than leaving it alone for
    financial trade data. Instead, any code that doesn't match the standard
    BR<digits> pattern is flagged for human review, with its closest
    look-alikes listed, but the underlying data is never silently rewritten."""
    cleaned = series.astype(str).str.strip().str.upper()
    canonical = sorted({c for c in cleaned.unique() if re.fullmatch(r"BR\d+", c)})
    flagged = []
    if canonical:
        for code in cleaned.unique():
            if code in canonical:
                continue
            close = difflib.get_close_matches(code, canonical, n=2, cutoff=0.6)
            flagged.append({"code": code, "occurrences": int((cleaned == code).sum()),
                             "possible_matches": ", ".join(close) if close else "none found"})
    return cleaned, flagged


def _read_any_table(source) -> pd.DataFrame:
    """Read a CSV or Excel source (path, file-like, or text buffer) and
    locate the header row containing 'Posting Date', mirroring how the
    original RSE export files are structured (extra title rows above the
    real header)."""
    name = getattr(source, "name", str(source))
    is_excel = str(name).lower().endswith((".xlsx", ".xls"))

    if is_excel:
        raw = pd.read_excel(source, sheet_name=0, header=None)
        header_row = None
        for i, row in raw.iterrows():
            if row.astype(str).str.strip().eq("Posting Date").any():
                header_row = i
                break
        if header_row is None:
            raise ValueError("Could not locate a 'Posting Date' header row in the uploaded Excel file.")
        header = raw.iloc[header_row]
        df = raw.iloc[header_row + 1:].copy()
        df.columns = header
        df = df.loc[:, [c for c in df.columns if pd.notna(c)]]
    else:
        df = pd.read_csv(source)

    df.columns = [str(c).strip() for c in df.columns]
    return df


@st.cache_data(show_spinner=False)
def load_data(source):
    """Load, validate, and clean an RSE trade log from any supported source
    (embedded text, local CSV path, or an uploaded CSV/XLSX file). Returns
    (cleaned_df, quality_report). Fully generic — no month-specific fixes."""
    df = _read_any_table(source)

    missing_cols = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing_cols:
        raise ValueError(
            f"The file is missing required column(s): {', '.join(missing_cols)}. "
            f"Expected columns: {', '.join(REQUIRED_COLS)}."
        )
    df = df[REQUIRED_COLS].copy()

    quality = {
        "missing_before": {}, "invalid_rows_dropped": 0, "duplicates_removed": 0,
        "flagged_broker_codes": [], "trimmed_security_names": 0,
    }

    df["Posting Date"] = pd.to_datetime(df["Posting Date"], errors="coerce")
    for col in REQUIRED_COLS:
        quality["missing_before"][col] = int(df[col].isna().sum())

    before = df["Security"].astype(str)
    df["Security"] = before.str.strip()
    quality["trimmed_security_names"] = int((before != df["Security"]).sum())

    df["Buyer Code"], buyer_flags = _standardize_broker_codes(df["Buyer Code"])
    df["Seller Code"], seller_flags = _standardize_broker_codes(df["Seller Code"])
    quality["flagged_broker_codes"] = buyer_flags + seller_flags

    for col in ["Quantity", "Price", "Turnover", "Deals"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    before_rows = len(df)
    df = df.dropna(subset=REQUIRED_COLS)
    quality["invalid_rows_dropped"] = before_rows - len(df)

    before_rows = len(df)
    df = df.drop_duplicates()
    quality["duplicates_removed"] = before_rows - len(df)

    df["Security Type"] = df["Security"].apply(classify_security)
    df["Trading Date"] = df["Posting Date"].dt.date
    df = df.sort_values("Posting Date").reset_index(drop=True)

    return df, quality


def period_label(min_date, max_date) -> str:
    """Human-friendly label for the dataset's date span — 'July 2026' if it's
    a single calendar month, else an explicit date range."""
    min_date, max_date = pd.Timestamp(min_date), pd.Timestamp(max_date)
    if (min_date.year, min_date.month) == (max_date.year, max_date.month):
        return min_date.strftime("%B %Y")
    return f"{min_date.strftime('%d %b %Y')} – {max_date.strftime('%d %b %Y')}"


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


def kpi_card(label, value_display, exact_display, bg=GREEN_DARK, unit=None):
    unit_html = f'<p class="kpi-unit">{unit}</p>' if unit else ""
    st.markdown(
        f"""
        <div class="kpi-card" style="background-color:{bg};" title="{exact_display}">
            <p class="kpi-label">{label}</p>
            {unit_html}
            <p class="kpi-value">{value_display}</p>
            <p class="kpi-exact">Exact: {exact_display}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def alert_box(message, level="info"):
    colors = {
        "green": ("rgba(30,132,73,0.18)", GREEN_LIGHT_TEXT),
        "gold": (GOLD_LIGHT, "#F0C24B"),
        "red": (RED_LIGHT, "#F1948A"),
        "info": ("rgba(59,110,166,0.18)", "#9EC2EC"),
    }
    bg, fg = colors.get(level, colors["info"])
    st.markdown(
        f'<div class="alert-box" style="background-color:{bg}; color:{fg};">{message}</div>',
        unsafe_allow_html=True,
    )


def safe_corr(x: pd.Series, y: pd.Series):
    paired = pd.concat([x, y], axis=1).dropna()
    n = len(paired)
    if n < 3 or paired.iloc[:, 0].std() == 0 or paired.iloc[:, 1].std() == 0:
        return None, n
    r = paired.iloc[:, 0].corr(paired.iloc[:, 1])
    return r, n

# ----------------------------------------------------------------------------
# SIDEBAR — DATA SOURCE (upload next month's file here — no code changes needed)
# ----------------------------------------------------------------------------
st.sidebar.markdown(
    f'<div style="display:flex; align-items:center; gap:8px;">'
    f'<span style="font-size:20px;">📊</span>'
    f'<span style="font-size:20px; font-weight:800;">RSE Dashboard</span></div>',
    unsafe_allow_html=True,
)

st.sidebar.markdown("#### 📤 Upload trading data")
uploaded_file = st.sidebar.file_uploader(
    "Drop next month's trade log (.csv or .xlsx)",
    type=["csv", "xlsx", "xls"],
    help=(
        "Expected columns: Posting Date, Buyer Code, Seller Code, Security, "
        "Quantity, Price, Turnover, Deals. The dashboard cleans, classifies, "
        "and re-generates every chart, KPI, and insight automatically — "
        "nothing needs to be rebuilt."
    ),
)

load_error = None
if uploaded_file is not None:
    try:
        df_raw, quality_report = load_data(uploaded_file)
        data_source_label = f"Uploaded: {uploaded_file.name}"
    except Exception as e:
        load_error = str(e)
        df_raw, quality_report = load_data(io.StringIO(EMBEDDED_CSV))
        data_source_label = "Built-in dataset (upload failed — see message above)"
else:
    DATA_PATH = Path(__file__).resolve().parent / "data" / "rse_trades_clean.csv"
    if DATA_PATH.exists():
        df_raw, quality_report = load_data(str(DATA_PATH))
        data_source_label = "data/rse_trades_clean.csv"
    else:
        df_raw, quality_report = load_data(io.StringIO(EMBEDDED_CSV))
        data_source_label = "Built-in dataset (embedded in app.py)"

if load_error:
    st.sidebar.error(f"Couldn't read that file: {load_error}\n\nShowing the built-in dataset instead.")

if df_raw.empty:
    st.error("The dataset loaded but contains no usable trade records.")
    st.stop()

MIN_DATE = df_raw["Posting Date"].min().date()
MAX_DATE = df_raw["Posting Date"].max().date()
PERIOD_LABEL = period_label(MIN_DATE, MAX_DATE)

st.sidebar.markdown(
    f'<div class="meta-line">Rwanda Stock Exchange · {PERIOD_LABEL}</div>',
    unsafe_allow_html=True,
)
st.sidebar.caption(f"Data source: {data_source_label}")
st.sidebar.markdown("---")

# ----------------------------------------------------------------------------
# SIDEBAR — FILTERS
# ----------------------------------------------------------------------------
st.sidebar.markdown("#### Posting Date range")
date_range = st.sidebar.date_input(
    "Posting Date range", value=(MIN_DATE, MAX_DATE), min_value=MIN_DATE, max_value=MAX_DATE,
    label_visibility="collapsed",
)
if isinstance(date_range, tuple) and len(date_range) == 2:
    date_start, date_end = date_range
else:
    date_start, date_end = MIN_DATE, MAX_DATE

st.sidebar.markdown("#### Security Type")
type_options = sorted(df_raw["Security Type"].unique())
selected_types = st.sidebar.multiselect("Security Type", type_options, default=type_options, label_visibility="collapsed")

st.sidebar.markdown("#### Security (Ticker / Name)")
security_options = sorted(df_raw["Security"].unique())
selected_securities = st.sidebar.multiselect(
    "Security", security_options, default=[], label_visibility="collapsed",
    format_func=security_display_name,
)

st.sidebar.markdown("#### Broker Code (Buyer Code / Seller Code)")
broker_options = sorted(set(df_raw["Buyer Code"]) | set(df_raw["Seller Code"]))
selected_brokers = st.sidebar.multiselect("Broker Code", broker_options, default=[], label_visibility="collapsed")

if st.sidebar.button("↺ Reset Filters", use_container_width=True):
    st.rerun()

mask = (df_raw["Trading Date"] >= date_start) & (df_raw["Trading Date"] <= date_end)
if selected_types:
    mask &= df_raw["Security Type"].isin(selected_types)
if selected_securities:
    mask &= df_raw["Security"].isin(selected_securities)
if selected_brokers:
    mask &= df_raw["Buyer Code"].isin(selected_brokers) | df_raw["Seller Code"].isin(selected_brokers)

df = df_raw.loc[mask].copy()

st.sidebar.markdown("---")
st.sidebar.caption(f"Showing **{len(df):,}** of {len(df_raw):,} deals.")

# ----------------------------------------------------------------------------
# HEADER
# ----------------------------------------------------------------------------
st.markdown("# Rwanda Stock Exchange Trading Dashboard")

st.markdown(
    f"""
    <div class="quote-box">
        <div class="quote-mark">&ldquo;</div>
        <div class="quote-text">
        The Rwanda Stock Exchange is the national securities exchange of Rwanda, providing a
        regulated marketplace for buying, selling, and listing financial instruments such as
        shares, corporate bonds, and government securities. It is an organized and regulated
        financial market where securities are bought and sold at prices governed by the forces
        of demand and supply.
        </div>
        <div class="quote-attrib">Rwanda Stock Exchange Ltd.</div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    f'<div class="meta-line">This dashboard analyzes every trade executed on the Exchange in '
    f'<b>{PERIOD_LABEL}</b>, covering Posting Date, Security, Buyer Code, Seller Code, Quantity, '
    f'Price, Turnover, and Deals for each transaction across both Equity and Debt Securities '
    f'listed on the Exchange.</div>',
    unsafe_allow_html=True,
)
st.markdown(
    f'<div class="meta-line">Posting Date range: {fmt_date(date_start)} – {fmt_date(date_end)} '
    f'· {len(df):,} deals shown (of {len(df_raw):,} total in the dataset)</div>',
    unsafe_allow_html=True,
)
st.markdown("")

if df.empty:
    st.warning("Not enough data is available for this analysis under the selected filters.")
    st.stop()

# ----------------------------------------------------------------------------
# SHARED AGGREGATES (used across tabs)
# ----------------------------------------------------------------------------
daily = df.groupby("Trading Date").agg(
    Turnover=("Turnover", "sum"), Volume=("Quantity", "sum"), Deals=("Deals", "sum"),
).reset_index().sort_values("Trading Date").reset_index(drop=True)
daily["Avg Deal Size"] = daily["Turnover"] / daily["Deals"].replace(0, np.nan)

sec_turnover = df.groupby("Security")["Turnover"].sum().sort_values(ascending=False)
sec_volume = df.groupby("Security")["Quantity"].sum().sort_values(ascending=False)
sec_deals = df.groupby("Security")["Deals"].sum().sort_values(ascending=False)

type_agg = df.groupby("Security Type").agg(
    Turnover=("Turnover", "sum"), Volume=("Quantity", "sum"), Deals=("Deals", "sum")
).reset_index()

total_turnover = df["Turnover"].sum()
total_volume = df["Quantity"].sum()
total_deals = df["Deals"].sum()
n_securities = df["Security"].nunique()
n_days = daily["Trading Date"].nunique()
avg_daily_turnover = daily["Turnover"].mean()
avg_daily_volume = daily["Volume"].mean()
avg_deal_size = total_turnover / total_deals if total_deals else np.nan
max_turnover_row = daily.loc[daily["Turnover"].idxmax()]
min_turnover_row = daily.loc[daily["Turnover"].idxmin()]
max_volume_row = daily.loc[daily["Volume"].idxmax()]
max_deals_row = daily.loc[daily["Deals"].idxmax()]
top_turnover_sec = sec_turnover.index[0]
top_volume_sec = sec_volume.index[0]
top_deals_sec = sec_deals.index[0]

var_df = daily.copy()
for col in ["Turnover", "Volume", "Deals"]:
    var_df[f"{col} Abs Change"] = var_df[col].diff()
    var_df[f"{col} % Change"] = var_df[col].pct_change() * 100

conc = (sec_turnover / sec_turnover.sum() * 100).sort_values(ascending=False)
top3_share = conc.head(3).sum()


def find_outliers_iqr(series, dates, label):
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

# ----------------------------------------------------------------------------
# TABS
# ----------------------------------------------------------------------------
(tab_overview, tab_trends, tab_comparisons, tab_distributions, tab_variations,
 tab_concentration, tab_alerts, tab_explorer, tab_about) = st.tabs([
    "📌 Overview & KPIs", "📈 Trends", "🏆 Comparisons", "📊 Distributions",
    "🔗 Variations & Correlations", "🎯 Concentration", "🔔 Alerts",
    "🗂️ Data Explorer", "⚖️ Ethics & Insights",
])

# ============================================================================
# TAB: OVERVIEW & KPIs
# ============================================================================
with tab_overview:
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        kpi_card("Total Turnover", fmt_rwf(total_turnover), fmt_exact_rwf(total_turnover), GREEN_DARK, unit="RWF")
    with k2:
        kpi_card("Total Deals", f"{total_deals:,}", f"{total_deals:,}", GREEN)
    with k3:
        kpi_card("Total Volume", fmt_qty(total_volume), f"{total_volume:,.0f}", GREEN_DARK, unit="Σ Quantity (units)")
    with k4:
        kpi_card("Avg Turnover / Deal", fmt_rwf(avg_deal_size), fmt_exact_rwf(avg_deal_size), GREEN, unit="RWF")

    k5, k6, k7, k8 = st.columns(4)
    with k5:
        kpi_card("Securities Traded", f"{n_securities}", f"{n_securities}", BLUE)
    with k6:
        kpi_card("Active Trading Days", f"{n_days}", f"{n_days}", BLUE)
    with k7:
        kpi_card("Avg Daily Turnover", fmt_rwf(avg_daily_turnover), fmt_exact_rwf(avg_daily_turnover), GREEN_DARK, unit="RWF")
    with k8:
        kpi_card("Avg Daily Volume", fmt_qty(avg_daily_volume), f"{avg_daily_volume:,.0f}", BLUE)

    k9, k10, k11 = st.columns(3)
    with k9:
        kpi_card("Highest Daily Turnover", fmt_rwf(max_turnover_row["Turnover"]),
                  f'{fmt_exact_rwf(max_turnover_row["Turnover"])} on {fmt_date(max_turnover_row["Trading Date"])}', GOLD)
    with k10:
        kpi_card("Highest Daily Volume", fmt_qty(max_volume_row["Volume"]),
                  f'{max_volume_row["Volume"]:,.0f} on {fmt_date(max_volume_row["Trading Date"])}', GREEN)
    with k11:
        kpi_card("Highest Deal Count", f'{int(max_deals_row["Deals"])}',
                  f'{int(max_deals_row["Deals"])} on {fmt_date(max_deals_row["Trading Date"])}', GREEN)

    st.markdown("### Market Summary")
    st.markdown(
        f"""
- **Strongest trading day:** {fmt_date(max_turnover_row['Trading Date'])} recorded the highest turnover
  ({fmt_rwf(max_turnover_row['Turnover'])}), indicating unusually strong market activity.
- **Weakest trading day:** {fmt_date(min_turnover_row['Trading Date'])} recorded the lowest turnover
  ({fmt_rwf(min_turnover_row['Turnover'])}) among active trading days.
- **Highest-turnover security:** **{security_display_name(top_turnover_sec)}** contributed {fmt_rwf(sec_turnover.iloc[0])}.
- **Highest-volume security:** **{security_display_name(top_volume_sec)}** with {fmt_qty(sec_volume.iloc[0])} units traded.
- **Most active security (by deals):** **{security_display_name(top_deals_sec)}** with {int(sec_deals.iloc[0])} deals.
"""
    )

# ============================================================================
# TAB: TRENDS
# ============================================================================
with tab_trends:
    st.markdown(
        '<div class="section-note">Every available trading day, in chronological order. '
        'Hover for exact values; use the toolbar to zoom, pan, or reset the view.</div>',
        unsafe_allow_html=True,
    )

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=daily["Trading Date"], y=daily["Turnover"], mode="lines+markers",
        line=dict(color=GREEN_BRIGHT, width=3), marker=dict(size=6),
        hovertemplate="<b>%{x|%d %b %Y}</b><br>Turnover: RWF %{y:,.0f}<extra></extra>",
    ))
    fig.update_layout(**PLOTLY_LAYOUT, title="Daily Turnover Trend (RWF)", xaxis_title="Trading Date",
                       yaxis_title="Turnover (RWF)", yaxis_tickformat=".2s", height=400)
    st.plotly_chart(fig, use_container_width=True)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=daily["Trading Date"], y=daily["Volume"], mode="lines+markers",
        line=dict(color=BLUE_LIGHT, width=3), marker=dict(size=6),
        hovertemplate="<b>%{x|%d %b %Y}</b><br>Volume: %{y:,.0f}<extra></extra>",
    ))
    fig.update_layout(**PLOTLY_LAYOUT, title="Daily Trading Volume", xaxis_title="Trading Date",
                       yaxis_title="Volume (units)", yaxis_tickformat=".2s", height=400)
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Higher trading volume indicates that more shares or securities were exchanged during the trading day.")

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=daily["Trading Date"], y=daily["Deals"], mode="lines+markers",
        line=dict(color=GOLD, width=3), marker=dict(size=6),
        hovertemplate="<b>%{x|%d %b %Y}</b><br>Deals: %{y:,}<extra></extra>",
    ))
    fig.update_layout(**PLOTLY_LAYOUT, title="Number of Deals by Trading Day", xaxis_title="Trading Date",
                       yaxis_title="Number of Deals", height=360)
    st.plotly_chart(fig, use_container_width=True)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=daily["Trading Date"], y=daily["Avg Deal Size"], mode="lines+markers",
        line=dict(color="#6FCF97", width=3), marker=dict(size=6),
        hovertemplate="<b>%{x|%d %b %Y}</b><br>Avg Deal Size: RWF %{y:,.0f}<extra></extra>",
    ))
    fig.update_layout(**PLOTLY_LAYOUT, title="Average Deal Size Trend (Turnover ÷ Deals)",
                       xaxis_title="Trading Date", yaxis_title="Avg Deal Size (RWF)",
                       yaxis_tickformat=".2s", height=360)
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Average deal size shows the typical value of a transaction. Days with zero deals are excluded.")

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
        fig = px.imshow(pivot, color_continuous_scale=[[0, "#12331F"], [0.5, GREEN], [1, GREEN_BRIGHT]], aspect="auto")
        fig.update_layout(**PLOTLY_LAYOUT, title=f"Daily {heat_metric} Heatmap (by Week / Weekday)", height=320)
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("### 🧾 Daily Market Summary Table")
    table_df = daily.copy()
    table_df["Trading Date"] = pd.to_datetime(table_df["Trading Date"]).dt.strftime("%d %b %Y")
    table_df = table_df.rename(columns={"Volume": "Volume (units)"})
    st.dataframe(table_df, use_container_width=True, height=300)
    st.download_button("⬇️ Download Daily Summary (CSV)", data=table_df.to_csv(index=False).encode("utf-8"),
                        file_name="rse_daily_summary.csv", mime="text/csv")

# ============================================================================
# TAB: COMPARISONS
# ============================================================================
with tab_comparisons:
    st.markdown("### Securities by Type (Turnover, Deals & Volume)")
    c1, c2, c3 = st.columns(3)
    type_colors = {"Bond": GREEN_BRIGHT, "Equity": BLUE_LIGHT}
    with c1:
        fig = px.bar(type_agg, x="Security Type", y="Turnover", color="Security Type",
                     color_discrete_map=type_colors, text="Turnover")
        fig.update_traces(texttemplate="RWF %{text:.2s}", textposition="outside")
        fig.update_layout(**PLOTLY_LAYOUT, title="Turnover", showlegend=True, height=380, yaxis_tickformat=".2s")
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        fig = px.bar(type_agg, x="Security Type", y="Deals", color="Security Type",
                     color_discrete_map=type_colors, text="Deals")
        fig.update_traces(texttemplate="%{text}", textposition="outside")
        fig.update_layout(**PLOTLY_LAYOUT, title="Deals", showlegend=True, height=380)
        st.plotly_chart(fig, use_container_width=True)
    with c3:
        fig = px.bar(type_agg, x="Security Type", y="Volume", color="Security Type",
                     color_discrete_map=type_colors, text="Volume")
        fig.update_traces(texttemplate="%{text:.2s}", textposition="outside")
        fig.update_layout(**PLOTLY_LAYOUT, title="Volume", showlegend=True, height=380, yaxis_tickformat=".2s")
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.markdown("### Top Securities")
    top_n = st.radio("Show top:", [5, 10, 15], index=1, horizontal=True)
    b1, b2, b3 = st.columns(3)
    with b1:
        top_t = sec_turnover.head(top_n).sort_values()
        fig = px.bar(top_t, x=top_t.values, y=[security_display_name(s) for s in top_t.index], orientation="h",
                     labels={"x": "Turnover (RWF)", "y": ""}, text=top_t.values)
        fig.update_traces(marker_color=GREEN_BRIGHT, texttemplate="RWF %{text:.2s}", textposition="outside",
                           hovertemplate="<b>%{y}</b><br>Turnover: RWF %{x:,.0f}<extra></extra>")
        fig.update_layout(**PLOTLY_LAYOUT, title=f"Top {top_n} by Turnover", height=420)
        st.plotly_chart(fig, use_container_width=True)
    with b2:
        top_v = sec_volume.head(top_n).sort_values()
        fig = px.bar(top_v, x=top_v.values, y=[security_display_name(s) for s in top_v.index], orientation="h",
                     labels={"x": "Volume", "y": ""}, text=top_v.values)
        fig.update_traces(marker_color=BLUE_LIGHT, texttemplate="%{text:.2s}", textposition="outside",
                           hovertemplate="<b>%{y}</b><br>Volume: %{x:,.0f}<extra></extra>")
        fig.update_layout(**PLOTLY_LAYOUT, title=f"Top {top_n} by Volume", height=420)
        st.plotly_chart(fig, use_container_width=True)
    with b3:
        top_d = sec_deals.head(top_n).sort_values()
        fig = px.bar(top_d, x=top_d.values, y=[security_display_name(s) for s in top_d.index], orientation="h",
                     labels={"x": "Deals", "y": ""}, text=top_d.values)
        fig.update_traces(marker_color=GOLD, texttemplate="%{text}", textposition="outside",
                           hovertemplate="<b>%{y}</b><br>Deals: %{x}<extra></extra>")
        fig.update_layout(**PLOTLY_LAYOUT, title=f"Top {top_n} by Deals", height=420)
        st.plotly_chart(fig, use_container_width=True)

# ============================================================================
# TAB: DISTRIBUTIONS
# ============================================================================
with tab_distributions:
    d1, d2, d3 = st.columns(3)
    with d1:
        fig = px.histogram(daily, x="Turnover", nbins=min(10, max(1, len(daily))), color_discrete_sequence=[GREEN_BRIGHT])
        fig.update_layout(**PLOTLY_LAYOUT, title="Daily Turnover Distribution", height=340)
        st.plotly_chart(fig, use_container_width=True)
    with d2:
        fig = px.histogram(daily, x="Volume", nbins=min(10, max(1, len(daily))), color_discrete_sequence=[BLUE_LIGHT])
        fig.update_layout(**PLOTLY_LAYOUT, title="Trading Volume Distribution", height=340)
        st.plotly_chart(fig, use_container_width=True)
    with d3:
        fig = px.histogram(daily, x="Deals", nbins=min(10, max(1, len(daily))), color_discrete_sequence=[GOLD])
        fig.update_layout(**PLOTLY_LAYOUT, title="Number of Deals Distribution", height=340)
        st.plotly_chart(fig, use_container_width=True)

    st.markdown(
        f"""
- **Typical turnover:** median day traded around {fmt_rwf(daily['Turnover'].median())}, spread
  (std. deviation) of {fmt_rwf(daily['Turnover'].std())}.
- **Typical volume:** median day saw {fmt_qty(daily['Volume'].median())} units traded.
- **Typical deal count:** median day recorded {daily['Deals'].median():.0f} deals.
"""
    )

    st.markdown("### 🚨 Outlier Analysis")
    if outlier_rows:
        st.dataframe(pd.DataFrame(outlier_rows), use_container_width=True)
        st.caption("An outlier is a value unusually high or low vs. the normal pattern "
                   "(IQR method: beyond 1.5× the interquartile range).")
    else:
        st.info("No statistically significant outliers were detected in daily Turnover, Volume, or Deals.")

# ============================================================================
# TAB: VARIATIONS & CORRELATIONS
# ============================================================================
with tab_variations:
    st.markdown("## Variations")
    st.markdown(
        "- **Absolute Change** = Current value − Previous value\n"
        "- **Percentage Change** = ((Current − Previous) / Previous) × 100"
    )
    var_metric = st.selectbox("Metric", ["Turnover", "Volume", "Deals"], key="var_metric")
    if len(var_df) < 2:
        st.info("Not enough data is available for this analysis under the selected filters.")
    else:
        colors = np.where(var_df[f"{var_metric} % Change"].fillna(0) >= 0, GREEN_BRIGHT, RED)
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=pd.to_datetime(var_df["Trading Date"]), y=var_df[f"{var_metric} % Change"], marker_color=colors,
            customdata=np.stack([var_df[var_metric], var_df[var_metric].shift(1), var_df[f"{var_metric} Abs Change"]], axis=-1),
            hovertemplate=("<b>%{x|%d %b %Y}</b><br>Current: %{customdata[0]:,.0f}<br>Previous: %{customdata[1]:,.0f}"
                            "<br>Absolute Change: %{customdata[2]:,.0f}<br>%% Change: %{y:.1f}%<extra></extra>"),
        ))
        fig.add_hline(y=0, line_color=TEXT_MUTED, line_width=1)
        fig.update_layout(**PLOTLY_LAYOUT, title=f"Daily {var_metric} % Change", xaxis_title="Trading Date",
                           yaxis_title="% Change", height=380)
        st.plotly_chart(fig, use_container_width=True)

        v1, v2, v3 = st.columns(3)
        std_val, mean_val = daily[var_metric].std(), daily[var_metric].mean()
        cv = (std_val / mean_val * 100) if mean_val else np.nan
        with v1:
            kpi_card(f"{var_metric} Std. Deviation", fmt_rwf(std_val) if var_metric != "Deals" else f"{std_val:,.1f}",
                      f"{std_val:,.2f}", BLUE)
        with v2:
            kpi_card("Coefficient of Variation", f"{cv:.1f}%" if pd.notna(cv) else "n/a",
                      f"{cv:.2f}%" if pd.notna(cv) else "n/a", GREEN_DARK)
        with v3:
            max_abs_move = var_df[f"{var_metric} % Change"].abs().max()
            kpi_card("Largest Swing", fmt_pct(max_abs_move) if pd.notna(max_abs_move) else "n/a",
                      fmt_pct(max_abs_move) if pd.notna(max_abs_move) else "n/a", GOLD)

    st.markdown("---")
    st.markdown("## Correlations & Relationships")
    corr_cols = ["Turnover", "Volume", "Deals", "Avg Deal Size"]
    corr_data = daily[corr_cols]
    if len(corr_data.dropna()) >= 3:
        corr_matrix = corr_data.corr(numeric_only=True)
        fig = px.imshow(corr_matrix, text_auto=".2f", color_continuous_scale=[[0, RED], [0.5, "#22262E"], [1, GREEN_BRIGHT]],
                         zmin=-1, zmax=1, aspect="auto")
        fig.update_layout(**PLOTLY_LAYOUT, title="Correlation Heatmap (Daily Aggregates)", height=380)
        st.plotly_chart(fig, use_container_width=True)
    else:
        alert_box("Not enough data is available for this analysis under the selected filters.", "gold")

    for x_col, y_col in [("Turnover", "Volume"), ("Turnover", "Deals"), ("Volume", "Deals")]:
        r, n = safe_corr(daily[x_col], daily[y_col])
        s1, s2 = st.columns([2, 1])
        with s1:
            try:
                fig = px.scatter(daily, x=x_col, y=y_col, trendline="ols" if r is not None else None,
                                  hover_data={"Trading Date": True})
            except Exception:
                fig = px.scatter(daily, x=x_col, y=y_col, hover_data={"Trading Date": True})
            fig.update_traces(marker=dict(size=9, color=GREEN_BRIGHT, line=dict(width=1, color=GREEN_DARK)),
                               selector=dict(mode="markers"))
            fig.update_layout(**PLOTLY_LAYOUT, title=f"{x_col} vs {y_col}", height=340)
            st.plotly_chart(fig, use_container_width=True)
        with s2:
            if r is None:
                st.info("Not enough data for this analysis under the selected filters.")
            else:
                strength = "strong" if abs(r) >= 0.7 else "moderate" if abs(r) >= 0.4 else "weak"
                direction = "positive" if r >= 0 else "negative"
                st.metric(f"Correlation ({x_col} vs {y_col})", f"{r:.2f}")
                st.caption(f"Observations: {n}")
                st.write(f"A correlation of {r:.2f} indicates a {strength} {direction} relationship.")
    st.markdown("**Correlation does not prove causation.**")

# ============================================================================
# TAB: CONCENTRATION
# ============================================================================
with tab_concentration:
    top_conc = conc.head(10).sort_values()
    fig = px.bar(top_conc, x=top_conc.values, y=[security_display_name(s) for s in top_conc.index], orientation="h",
                 text=top_conc.values, labels={"x": "% of Total Turnover", "y": ""})
    fig.update_traces(marker_color=GREEN_BRIGHT, texttemplate="%{text:.1f}%", textposition="outside",
                       hovertemplate="<b>%{y}</b><br>Share of Turnover: %{x:.1f}%<extra></extra>")
    fig.update_layout(**PLOTLY_LAYOUT, title="Turnover Contribution by Security (Top 10)", height=420)
    st.plotly_chart(fig, use_container_width=True)
    st.markdown(
        f"**{security_display_name(conc.index[0])}** contributed **{conc.iloc[0]:.1f}%** of total turnover. "
        f"The top 3 securities together accounted for **{top3_share:.1f}%**, "
        f"{'indicating a concentrated market' if top3_share > 60 else 'indicating fairly distributed activity'}."
    )

# ============================================================================
# TAB: ALERTS
# ============================================================================
with tab_alerts:
    alert_box(f"📈 <b>Highest Turnover Day:</b> {fmt_date(max_turnover_row['Trading Date'])} — {fmt_rwf(max_turnover_row['Turnover'])}", "green")
    alert_box(f"📉 <b>Lowest Turnover Day:</b> {fmt_date(min_turnover_row['Trading Date'])} — {fmt_rwf(min_turnover_row['Turnover'])}", "info")
    alert_box(f"🔊 <b>Highest Volume Day:</b> {fmt_date(max_volume_row['Trading Date'])} — {fmt_qty(max_volume_row['Volume'])} units", "green")
    alert_box(f"🤝 <b>Highest Deal Count:</b> {fmt_date(max_deals_row['Trading Date'])} — {int(max_deals_row['Deals'])} deals", "info")

    if len(var_df) >= 2:
        max_swing = var_df["Turnover % Change"].abs().max()
        if pd.notna(max_swing) and max_swing > 100:
            swing_row = var_df.loc[var_df["Turnover % Change"].abs().idxmax()]
            alert_box(f"⚠️ <b>Large Turnover Variation:</b> {fmt_date(swing_row['Trading Date'])} saw a "
                      f"{fmt_pct(swing_row['Turnover % Change'])} change vs. the previous trading day.",
                      "gold" if max_swing < 300 else "red")

    if top3_share > 70:
        alert_box(f"⚠️ <b>High Market Concentration:</b> Top 3 securities account for {top3_share:.1f}% of turnover.", "gold")

    if outlier_rows:
        alert_box(f"🔍 <b>Outliers Detected:</b> {len(outlier_rows)} daily observation(s) flagged — see Distributions.", "gold")

    flagged = quality_report.get("flagged_broker_codes", [])
    if flagged or quality_report["invalid_rows_dropped"] or quality_report["duplicates_removed"]:
        alert_box(
            f"ℹ️ <b>Data Quality Note:</b> {len(flagged)} non-standard broker code(s) flagged for review, "
            f"{quality_report['duplicates_removed']} duplicate row(s), and {quality_report['invalid_rows_dropped']} "
            f"invalid row(s) were found. See the Ethics &amp; Insights tab for details.", "info",
        )

# ============================================================================
# TAB: DATA EXPLORER
# ============================================================================
with tab_explorer:
    e1, e2, e3, e4 = st.columns(4)
    e1.metric("Rows", f"{len(df):,}")
    e2.metric("Columns", f"{df.shape[1]}")
    e3.metric("Date Range", f"{fmt_date(date_start)} – {fmt_date(date_end)}")
    e4.metric("Missing Values", f"{int(df.isna().sum().sum())}")

    available_cols = list(df.columns)
    selected_cols = st.multiselect("Columns to display", available_cols, default=available_cols)
    search_term = st.text_input("Search (Security, Buyer Code, or Seller Code)")

    explorer_df = df[selected_cols].copy() if selected_cols else df.copy()
    if search_term:
        text_cols = [c for c in ["Security", "Buyer Code", "Seller Code"] if c in explorer_df.columns]
        if text_cols:
            cond = np.zeros(len(explorer_df), dtype=bool)
            for c in text_cols:
                cond |= explorer_df[c].astype(str).str.contains(search_term, case=False, na=False)
            explorer_df = explorer_df[cond]

    st.dataframe(explorer_df, use_container_width=True, height=340)
    st.download_button("⬇️ Download Filtered Data (CSV)", data=explorer_df.to_csv(index=False).encode("utf-8"),
                        file_name="rse_filtered.csv", mime="text/csv")

# ============================================================================
# TAB: ETHICS & INSIGHTS (Insights + Recommendations + Ethics/Data Quality + Glossary)
# ============================================================================
with tab_about:
    st.markdown("## 💡 Key Insights")
    turnover_trend = "increased" if daily["Turnover"].iloc[-1] > daily["Turnover"].iloc[0] else "decreased"
    vol_turnover_r, _ = safe_corr(daily["Volume"], daily["Turnover"])
    deals_turnover_r, _ = safe_corr(daily["Deals"], daily["Turnover"])
    st.markdown(
        f"""
> **Market Activity:** Trading activity fluctuated throughout {PERIOD_LABEL}, with the highest
> turnover on {fmt_date(max_turnover_row['Trading Date'])} and the lowest on {fmt_date(min_turnover_row['Trading Date'])}.

> **Market Concentration:** **{security_display_name(conc.index[0])}** alone accounted for {conc.iloc[0]:.1f}% of
> total turnover; the top 3 securities made up {top3_share:.1f}%.

> **Trading Volume:** {"Higher-volume days were generally associated with higher turnover" if vol_turnover_r and vol_turnover_r > 0.4 else "Volume and turnover did not show a strong consistent relationship"} (correlation: {f"{vol_turnover_r:.2f}" if vol_turnover_r is not None else "n/a"}).

> **Deal Activity:** {"More transactions tended to coincide with higher turnover" if deals_turnover_r and deals_turnover_r > 0.4 else "Deal count did not strongly track turnover"} (correlation: {f"{deals_turnover_r:.2f}" if deals_turnover_r is not None else "n/a"}).

> **Outliers:** {"Statistical outliers were detected — see Distributions for specifics." if outlier_rows else "No significant statistical outliers were found."}

> **Overall Direction:** Turnover {turnover_trend} from {fmt_rwf(daily['Turnover'].iloc[0])} on {fmt_date(daily['Trading Date'].iloc[0])} to {fmt_rwf(daily['Turnover'].iloc[-1])} on {fmt_date(daily['Trading Date'].iloc[-1])}.
"""
    )

    st.markdown("## 📋 Recommendations")
    st.markdown(
        f"""
- **Market Monitoring:** Track activity around {fmt_date(max_turnover_row['Trading Date'])}-type peaks to
  understand what drives unusually strong trading days.
- **Liquidity:** With **{security_display_name(top_deals_sec)}** and **{security_display_name(top_volume_sec)}**
  among the most active, monitor whether liquidity is broad-based across the security list.
- **Market Concentration:** With the top 3 securities at {top3_share:.1f}% of turnover, consider measures to
  encourage trading in a wider range of securities.
- **Unusual Activity:** Investigate flagged outlier days to confirm genuine market events vs. data issues.
- **Data Quality:** Keep enforcing consistent security/broker code formatting at entry.
"""
    )

    st.markdown("---")
    st.markdown("## ⚖️ Ethics & Data Quality")
    q1, q2, q3 = st.columns(3)
    q1.metric("Broker codes flagged for review", len(quality_report.get("flagged_broker_codes", [])))
    q2.metric("Duplicate rows removed", quality_report["duplicates_removed"])
    q3.metric("Invalid rows dropped", quality_report["invalid_rows_dropped"])
    if quality_report.get("flagged_broker_codes"):
        st.write(
            "⚠️ These codes don't match the standard `BR<digits>` pattern and were **not** "
            "auto-corrected (fuzzy-matching short codes is unreliable and risks silently "
            "misattributing a trade to the wrong broker) — please verify manually:"
        )
        st.dataframe(pd.DataFrame(quality_report["flagged_broker_codes"]), use_container_width=True)
    missing_summary = {k: v for k, v in quality_report["missing_before"].items() if v}
    st.write("Missing values before cleaning:", missing_summary if missing_summary else "None found.")
    st.markdown(
        """
- Data is presented accurately, based only on records in the uploaded/selected trade log.
- **Correlation does not prove causation** — relationships shown are observational, not causal.
- Flagged outliers require investigation before being treated as errors or genuine events.
- Insights here support, rather than replace, professional analytical judgment.
"""
    )

    st.markdown("---")
    st.markdown("## 📖 Glossary")
    glossary = {
        "RSE": "The Rwanda Stock Exchange — Rwanda's national, regulated securities market.",
        "Turnover": "The total monetary value of securities traded (Quantity × Price).",
        "Trading Volume": "The total number of shares/units of a security that changed hands.",
        "Number of Deals": "The count of individual transactions executed.",
        "Average Deal Size": "Total turnover divided by number of deals.",
        "Equity Security": "A listed company share (e.g. Bank of Kigali, Bralirwa, MTN Rwandacell).",
        "Debt Security / Bond": "A government or corporate bond paying interest over a defined term.",
        "Liquidity": "How easily a security can be bought/sold without moving its price.",
        "Volatility": "The degree of variation in a metric over time.",
        "Correlation": "A statistical measure (-1 to +1) of how two variables move together.",
        "Outlier": "A value unusually high or low vs. the normal pattern of the data.",
        "Market Concentration": "The degree to which activity is dominated by a few securities.",
    }
    g1, g2 = st.columns(2)
    items = list(glossary.items())
    half = len(items) // 2 + len(items) % 2
    for term, definition in items[:half]:
        g1.markdown(f"**{term}:** {definition}")
    for term, definition in items[half:]:
        g2.markdown(f"**{term}:** {definition}")

    st.markdown("---")
    st.caption("Rwanda Stock Exchange Trading Dashboard · Built with Streamlit & Plotly")
