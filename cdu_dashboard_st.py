"""
Gen3 CDU CW — Log Dashboard (Streamlit)
========================================
Run:   py -m streamlit run cdu_dashboard_st.py
Share: upload to Streamlit Community Cloud (free) or run on an internal server
"""

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
import os, glob, re, json, zipfile, tempfile, shutil
try:
    import py7zr
    _HAS_PY7ZR = True
except ImportError:
    _HAS_PY7ZR = False
from pathlib import Path
from collections import defaultdict

# ─────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Gen3 CDU CW — Log Dashboard",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# GLOBAL CSS — dark engineering theme
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Typography ─────────────────────────────────────────── */
* { font-family: 'Inter','Segoe UI',system-ui,-apple-system,sans-serif !important; }

/* ── Layout ─────────────────────────────────────────────── */
.block-container {
    padding-top: 4.5rem !important;
    padding-left: 2rem !important;
    padding-right: 2rem !important;
    max-width: 100% !important;
}

/* ── Sidebar ─────────────────────────────────────────────── */
[data-testid="stSidebar"] > div:first-child {
    background: #0a0e14 !important;
    border-right: 1px solid #1e2733 !important;
}

/* ── Tabs ────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
    background: rgba(13,17,23,0.9) !important;
    border-radius: 10px !important;
    padding: 4px 6px !important;
    gap: 2px !important;
    border: 1px solid #21262d !important;
    margin-bottom: 0.75rem !important;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 7px !important;
    padding: 7px 16px !important;
    font-weight: 500 !important;
    font-size: 0.82rem !important;
    color: #8b949e !important;
    background: transparent !important;
    border: none !important;
    transition: all 0.18s ease !important;
}
.stTabs [data-baseweb="tab"]:hover {
    color: #e6edf3 !important;
    background: rgba(255,255,255,0.06) !important;
}
[data-baseweb="tab"][aria-selected="true"] {
    background: rgba(31,111,235,0.16) !important;
    color: #58a6ff !important;
}
.stTabs [data-baseweb="tab-highlight"] {
    background: #1f6feb !important;
    height: 2px !important;
    border-radius: 2px !important;
}
.stTabs [data-baseweb="tab-border"] { display: none !important; }

/* ── KPI card columns ────────────────────────────────────── */
.block-container .stHorizontalBlock:first-of-type .stColumn {
    background: rgba(22,27,34,0.7) !important;
    border: 1px solid #21262d !important;
    border-radius: 10px !important;
    padding: 0.75rem 1rem !important;
    transition: border-color 0.2s, background 0.2s !important;
    overflow: hidden !important;
}
.block-container .stHorizontalBlock:first-of-type .stColumn:hover {
    background: rgba(31,36,44,0.9) !important;
    border-color: #30363d !important;
}
/* Semantic left-border accent per column */
.block-container .stHorizontalBlock:first-of-type .stColumn:nth-child(1) { border-left: 3px solid #58a6ff !important; }
.block-container .stHorizontalBlock:first-of-type .stColumn:nth-child(2) { border-left: 3px solid #3fb950 !important; }
.block-container .stHorizontalBlock:first-of-type .stColumn:nth-child(3) { border-left: 3px solid #ffa657 !important; }
.block-container .stHorizontalBlock:first-of-type .stColumn:nth-child(4) { border-left: 3px solid #bc8cff !important; }
.block-container .stHorizontalBlock:first-of-type .stColumn:nth-child(5) { border-left: 3px solid #79c0ff !important; }
.block-container .stHorizontalBlock:first-of-type .stColumn:nth-child(6) { border-left: 3px solid #3fb950 !important; }
.block-container .stHorizontalBlock:first-of-type .stColumn:nth-child(7) { border-left: 3px solid #56d364 !important; }

/* ── Metric component ────────────────────────────────────── */
[data-testid="stMetricValue"] {
    font-size: 1.55rem !important;
    font-weight: 700 !important;
    color: #e6edf3 !important;
    letter-spacing: -0.02em !important;
    white-space: pre-line !important;
    line-height: 1.3 !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    display: block !important;
}
[data-testid="stMetricLabel"] {
    font-size: 0.68rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.07em !important;
    color: #8b949e !important;
    font-weight: 500 !important;
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
}
[data-testid="stMetricDelta"] { display: none !important; }
/* Running Since col — slightly smaller so date + time fit on two lines */
.block-container .stHorizontalBlock:first-of-type .stColumn:nth-child(1) [data-testid="stMetricValue"] {
    font-size: 1.05rem !important;
    letter-spacing: 0 !important;
    line-height: 1.45 !important;
}

/* ── KPI label (custom) — single source of truth ─────────── */
.kpi-label {
    font-size: 0.68rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.07em !important;
    color: #8b949e !important;
    margin: 0 0 0.35rem 0 !important;
    font-weight: 500 !important;
    line-height: 1.4 !important;
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
}

/* ── Chart panels ────────────────────────────────────────── */
[data-testid="stPlotlyChart"] > div {
    border-radius: 10px !important;
    border: 1px solid #21262d !important;
    overflow: hidden !important;
    background: rgba(13,17,23,0.55) !important;
}

/* ── Dataframe ───────────────────────────────────────────── */
[data-testid="stDataFrame"] {
    border-radius: 8px !important;
    border: 1px solid #21262d !important;
    overflow: hidden !important;
}
iframe[title="streamlit_bokeh_events.streamlit_bokeh_events"] { display: none; }

/* ── Dividers ────────────────────────────────────────────── */
hr { border-color: #21262d !important; margin: 0.75rem 0 !important; }

/* ── Expanders ───────────────────────────────────────────── */
[data-testid="stExpander"] {
    border: 1px solid #21262d !important;
    border-radius: 8px !important;
    background: rgba(22,27,34,0.5) !important;
    margin-bottom: 0.5rem !important;
}
[data-testid="stExpander"] summary {
    font-weight: 500 !important;
    color: #c9d1d9 !important;
}

/* ── Alert boxes ─────────────────────────────────────────── */
[data-testid="stAlert"] { border-radius: 8px !important; }

/* ── Sidebar stat rows ───────────────────────────────────── */
.sidebar-stat {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 5px 0;
    border-bottom: 1px solid #1e2733;
    font-size: 0.83rem;
}
.sidebar-stat-label { color: #8b949e; }
.sidebar-stat-value { color: #e6edf3; font-weight: 600; font-variant-numeric: tabular-nums; }

/* ── Section subheaders ──────────────────────────────────── */
.section-header {
    font-size: 0.78rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #8b949e;
    margin: 0.5rem 0 0.75rem 0;
    padding-bottom: 0.4rem;
    border-bottom: 1px solid #21262d;
}

/* ── Developer footer ────────────────────────────────────── */
.dev-footer {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    height: 26px;
    background: rgba(10, 14, 20, 0.97);
    border-top: 1px solid #21262d;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    font-family: 'Inter','Segoe UI',system-ui,sans-serif;
    font-size: 0.70rem;
    color: #4a5568;
    letter-spacing: 0.05em;
    z-index: 99999;
    pointer-events: none;
    user-select: none;
}
.dev-footer .dev-name  { color: #6e7681; font-weight: 600; }
.dev-footer .dev-sep   { color: #30363d; }
.dev-footer .dev-copy  { color: #3d444d; }

/* ── Extra bottom padding so footer doesn't overlap content ─ */
.block-container { padding-bottom: 2.5rem !important; }
</style>
""", unsafe_allow_html=True)

st.markdown(
    '<div class="dev-footer">'
    '<span class="dev-copy">&#169; 2026</span>'
    '<span class="dev-sep">·</span>'
    '<span class="dev-name">Developed by Avinash Prodduturi</span>'
    '<span class="dev-sep">·</span>'
    '<span class="dev-copy">Delta Electronics &mdash; Thermal FAE</span>'
    '</div>',
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────────────────────────────────────────
# COLUMN GROUPS
# ─────────────────────────────────────────────────────────────────────────────
ALARM_COLS = [
    "Primary Return Temperature Abnormal","Primary Return Pressure Abnormal",
    "Secondary Return Temperature Abnormal","Secondary Return Pressure Abnormal",
    "Primary Supply Temperature Abnormal","Primary Supply Pressure Abnormal",
    "Secondary Supply Temperature Abnormal","Secondary Supply Pressure Abnormal",
    "Primary Flow Rate Abnormal","Secondary Flow Rate Abnormal",
    "Ambient Temperature Sensor Abnormal","Leakage Abnormal","Reservoir Abnormal","Sensor Abnormal",
    "Pump 1 Abnormal","Pump 2 Abnormal","Pump 3 Abnormal",
    "Fan 1 Abnormal","Fan 2 Abnormal","Dew Point Abnormal",
    "Leakage Abnormal 1","Leakage Abnormal 2","Leakage Abnormal 3",
    "Leakage Abnormal 4","Leakage Abnormal 5","Leakage Abnormal 6",
    "Leakage Unconnect 1 Abnormal","Leakage Unconnect 2 Abnormal",
    "Leakage Unconnect 3 Abnormal","Leakage Unconnect 4 Abnormal",
    "Leakage Unconnect 5 Abnormal","Leakage Unconnect 6 Abnormal",
]
TEMP_COLS  = ["Primary Supply Temperature Reading","Primary Return Temperature Reading",
              "Secondary Supply Temperature Reading","Secondary Return Temperature Reading",
              "Ambient Temperature Reading","Dew Point Reading"]
PRES_COLS  = ["Primary Supply Pressure Reading","Primary Return Pressure Reading",
              "Secondary Supply Pressure Reading","Secondary Return Pressure Reading"]
FLOW_COLS  = ["Primary Flow Reading","Secondary Flowrate Reading"]
PUMP_COLS  = ["Pump 1 Speed Reading","Pump 2 Speed Reading","Pump 3 Speed Reading","Pump Duty Reading"]
FAN_COLS   = ["Fan 1 Speed Reading","Fan 2 Speed Reading","Fan Duty Reading"]
POWER_COLS = ["Total Power Consumption Reading","Heat Removal Reading","Input Voltage Reading"]
VALVE_COLS = ["Valve Bypass Reading"]

PAL = ["#58a6ff","#bc8cff","#79c0ff","#3fb950","#e3b341","#f85149","#ffa657","#56d364"]

_GRID  = "#1e2733"
_AXIS  = "#30363d"
_TICK  = "#6e7681"
_TEXT  = "#c9d1d9"

CHART = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(13,17,23,0.55)",
    font=dict(color=_TEXT, size=11, family="Inter,'Segoe UI',system-ui,sans-serif"),
    margin=dict(l=60, r=56, t=52, b=44),
    legend=dict(
        bgcolor="rgba(13,17,23,0.88)",
        bordercolor=_AXIS,
        borderwidth=1,
        orientation="h",
        yanchor="bottom", y=1.02,
        xanchor="left", x=0,
        font=dict(size=11, color=_TEXT),
    ),
    hovermode="x unified",
    hoverlabel=dict(
        bgcolor="#1c2128",
        bordercolor=_AXIS,
        font=dict(color="#e6edf3", size=12),
    ),
    xaxis=dict(
        gridcolor=_GRID, gridwidth=1,
        linecolor=_AXIS, tickcolor=_AXIS,
        tickfont=dict(color=_TICK, size=10),
        zerolinecolor=_GRID,
        showspikes=True, spikecolor="#58a6ff",
        spikesnap="cursor", spikemode="across",
        spikethickness=1, spikedash="dot",
    ),
    yaxis=dict(
        gridcolor=_GRID, gridwidth=1,
        linecolor=_AXIS, tickcolor=_AXIS,
        tickfont=dict(color=_TICK, size=10),
        zerolinecolor=_GRID,
    ),
)

# Multi-subplot legend/margin presets
# y=1.07: sits above the rangeselector row (y≈1.00–1.03) with a clear gap
# t=220:  guarantees enough top margin for rangeselector buttons + legend row
_MULTI_LEGEND = dict(
    orientation="h", yanchor="bottom", y=1.07,
    xanchor="left", x=0,
    bgcolor="rgba(13,17,23,0.88)",
    bordercolor=_AXIS, borderwidth=1,
    tracegroupgap=4, itemsizing="constant",
    font=dict(size=10.5, color=_TEXT),
)
_MULTI_MARGIN = dict(l=60, r=56, t=220, b=70)

_SUBPLOT_TITLE_FONT = dict(size=12, color=_TEXT)

def style_fig(fig):
    """Apply consistent dark-theme axis styling to every axis in a figure."""
    ax = dict(
        gridcolor=_GRID, gridwidth=1,
        linecolor=_AXIS, tickcolor=_AXIS,
        tickfont=dict(color=_TICK, size=10),
        zerolinecolor=_GRID,
        showspikes=True, spikecolor="#58a6ff",
        spikesnap="cursor", spikemode="across",
        spikethickness=1, spikedash="dot",
    )
    fig.update_xaxes(**ax)
    fig.update_yaxes(
        gridcolor=_GRID, gridwidth=1,
        linecolor=_AXIS, tickcolor=_AXIS,
        tickfont=dict(color=_TICK, size=10),
        zerolinecolor=_GRID,
    )
    # Style subplot section titles (annotations)
    for ann in fig.layout.annotations:
        ann.update(font=_SUBPLOT_TITLE_FONT)
    return fig

# ─────────────────────────────────────────────────────────────────────────────
# CHART INTERACTION — single source of truth for all plotly_chart() calls
# ─────────────────────────────────────────────────────────────────────────────
# scrollZoom=False: the scroll wheel scrolls the PAGE, not the chart.
# This is the fix for both "can't scroll past charts" and
# "all charts zoom at once when I scroll".
# Users zoom via: drag a box on the chart  |  toolbar +/- buttons  |
#                 rangeselector buttons (time series)  |  double-click to reset
PLOTLY_CONFIG = {
    "scrollZoom": False,
    "displayModeBar": True,
    "displaylogo": False,
    "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d"],
    "toImageButtonOptions": {"format": "png", "filename": "cdu_chart", "scale": 2},
}

# Time-range quick-select buttons — added to every time-series subplot chart
_RS_BUTTONS = [
    dict(count=1,  label="1 hr",   step="hour", stepmode="backward"),
    dict(count=6,  label="6 hr",   step="hour", stepmode="backward"),
    dict(count=1,  label="1 day",  step="day",  stepmode="backward"),
    dict(count=7,  label="7 days", step="day",  stepmode="backward"),
    dict(step="all", label="All"),
]
_RS_STYLE = dict(
    bgcolor="rgba(13,17,23,0.95)",
    activecolor="#1f6feb",
    bordercolor=_AXIS,
    borderwidth=1,
    font=dict(color=_TEXT, size=10),
)

def add_rangeselector(fig, row=1, col=1):
    """Add time-range quick-select buttons to a subplot's top x-axis.
    Sits just above the plot area (y=1.0) leaving the legend clear at y=1.07.
    For single-axis charts pass row=None to target the only xaxis."""
    kwargs = dict(rangeselector=dict(buttons=_RS_BUTTONS, **_RS_STYLE))
    if row is None:
        fig.update_xaxes(**kwargs)
    else:
        fig.update_xaxes(**kwargs, row=row, col=col)

def add_rangeslider(fig):
    """Add a drag-handle range slider below a single-panel time-series chart."""
    fig.update_xaxes(
        rangeslider=dict(
            visible=True,
            thickness=0.07,
            bgcolor="#0d1117",
            bordercolor=_AXIS,
            borderwidth=1,
        )
    )

def short(col):
    for s in [" Reading"," Abnormal"," Setpoint"," Enabled/Disabled"]:
        col = col.replace(s, "")
    return col

def downsample(df, n=2000):
    if df is None or df.empty or len(df) <= n: return df
    step = max(1, len(df) // n)
    sampled = df.iloc[::step]
    # Always include the last row so charts reach the end of the time range
    if sampled.index[-1] != df.index[-1]:
        sampled = pd.concat([sampled, df.iloc[[-1]]])
    return sampled

def active_alarms(df):
    existing = [c for c in ALARM_COLS if c in df.columns]
    if not existing:
        return []
    sums = df[existing].sum()          # single vectorized pass
    return [(c, int(sums[c])) for c in existing if sums[c] > 0]

# ─────────────────────────────────────────────────────────────────────────────
# PARSERS  (cached so re-runs don't re-read files)
# ─────────────────────────────────────────────────────────────────────────────
def read_text(path):
    for enc in ("utf-8","utf-8-sig","latin-1","cp1252"):
        try:
            with open(path, "r", encoding=enc, errors="replace") as f:
                return f.read()
        except: pass
    return ""

def read_tail(path, max_bytes=500_000):
    size = os.path.getsize(path)
    for enc in ("utf-8","utf-8-sig","latin-1","cp1252"):
        try:
            with open(path, "r", encoding=enc, errors="replace") as f:
                if size > max_bytes:
                    f.seek(size - max_bytes)
                    f.readline()
                return f.readlines()
        except: pass
    return []

@st.cache_data(show_spinner=False)
def load_system_logs(unit_path):
    cdu   = os.path.join(unit_path, "cdu")
    files = sorted(glob.glob(os.path.join(cdu, "system_log*.csv")))
    if not files: return pd.DataFrame()
    frames = []
    for fp in files:
        try:
            df = pd.read_csv(fp, low_memory=False)
            df["_src"] = os.path.basename(fp)
            frames.append(df)
        except Exception as e:
            st.warning(f"Could not read {fp}: {e}")
    if not frames: return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)
    out["Timestamp"] = pd.to_datetime(out["Timestamp"], errors="coerce")
    out = out.dropna(subset=["Timestamp"])
    # Drop clearly bogus timestamps (before 2020 or epoch/reset values)
    out = out[out["Timestamp"] >= "2020-01-01"]
    return out.sort_values("Timestamp").reset_index(drop=True)

@st.cache_data(show_spinner=False)
def parse_alert_log(unit_path):
    path = os.path.join(unit_path, "cdu", "alert_log_1.log")
    if not os.path.exists(path): return pd.DataFrame()
    text = read_text(path)
    pat  = re.compile(r'\[(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\]\s+(.+?)\s+(asserted|deasserted)', re.I)
    matches = list(pat.finditer(text))
    if not matches: return pd.DataFrame()
    rows = [{"_ts": m.group(1), "Alarm": m.group(2).strip(), "State": m.group(3).lower()}
            for m in matches]
    df = pd.DataFrame(rows)
    df["Timestamp"] = pd.to_datetime(df["_ts"], errors="coerce")   # batch conversion — 1 call vs N
    return df.drop(columns=["_ts"]).dropna(subset=["Timestamp"]).sort_values("Timestamp").reset_index(drop=True)

@st.cache_data(show_spinner=False)
def parse_api_access(unit_path):
    cdu   = os.path.join(unit_path, "cdu")
    files = sorted(glob.glob(os.path.join(cdu, "api_access.log*")))
    if not files: return pd.DataFrame()
    pat = re.compile(
        r'(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})\s+-\s+(INFO|ERROR|WARN\w*)\s+-\s+'
        r'(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\s+(/[^\s]+)\s+-\s+(\d+)\s+-\s+([\d.]+)ms\s+-\s+([\S]+)'
    )
    rows = []
    for fp in sorted(files, reverse=True):
        for line in read_tail(fp, 300_000):
            m = pat.search(line)
            if m:
                rows.append({"_ts": m.group(1), "Level": m.group(2),
                             "Method": m.group(3), "Endpoint": m.group(4),
                             "Status": int(m.group(5)), "ResponseMs": float(m.group(6)),
                             "Client": m.group(7).replace("::ffff:",""), "_file": os.path.basename(fp)})
    if not rows: return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["Timestamp"] = pd.to_datetime(df["_ts"], errors="coerce")   # batch conversion — 1 call vs N
    return df.drop(columns=["_ts"]).dropna(subset=["Timestamp"]).drop_duplicates().sort_values("Timestamp").reset_index(drop=True)

@st.cache_data(show_spinner=False)
def parse_event_log(unit_path):
    path = os.path.join(unit_path, "cdu", "event_log_1.log")
    if not os.path.exists(path): return pd.DataFrame()
    text   = read_text(path)
    ts_pat = re.compile(r'(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2})')
    rows   = []
    for line in text.splitlines():
        if not line.strip(): continue
        m = ts_pat.search(line)
        rows.append({"_ts": m.group(1) if m else None, "Message": line.strip()})
    if not rows: return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["Timestamp"] = pd.to_datetime(df["_ts"], errors="coerce")  # batch conversion — 1 call vs N
    return df.drop(columns=["_ts"]).dropna(subset=["Timestamp"]).sort_values("Timestamp").reset_index(drop=True)

VERBOSE_TARGETS = ["cdu_app.log","web_app.log","modbus_tcp_server.log","modbus_rtu_server.log",
                   "metadata_app.log","update_log_manager.log","log_manager.log",
                   "di_manager.log","certificate.log"]

@st.cache_data(show_spinner=False)
def parse_verbose_logs(unit_path):
    vdir = os.path.join(unit_path, "verbose_logs")
    if not os.path.isdir(vdir): return pd.DataFrame()
    files = []
    for base in VERBOSE_TARGETS:
        files += sorted(glob.glob(os.path.join(vdir, base + "*")))
    ts_pat  = re.compile(r'(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?)')
    lvl_pat = re.compile(r'\b(ERROR|WARN(?:ING)?|INFO|DEBUG|CRITICAL|FATAL)\b', re.I)
    rows = []
    for fp in files:
        if os.path.getsize(fp) == 0: continue
        log_name = re.sub(r'\.\d+$', '', os.path.basename(fp))
        for line in read_tail(fp, 400_000):
            line = line.strip()
            if not line: continue
            ts_m = ts_pat.search(line)
            if not ts_m: continue
            lvl_m = lvl_pat.search(line)
            rows.append({"_ts": ts_m.group(1),
                         "Level": lvl_m.group(1).upper() if lvl_m else "INFO",
                         "Log": log_name, "Message": line[:300]})
    if not rows: return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["Timestamp"] = pd.to_datetime(df["_ts"], errors="coerce")  # batch conversion — 1 call vs N
    return df.drop(columns=["_ts"]).dropna(subset=["Timestamp"]).sort_values("Timestamp").reset_index(drop=True)

@st.cache_data(show_spinner=False)
def parse_event_txts(unit_path):
    vdir = os.path.join(unit_path, "verbose_logs")
    if not os.path.isdir(vdir): return []
    return [{"file": os.path.basename(fp), "content": read_text(fp).strip()}
            for fp in sorted(glob.glob(os.path.join(vdir, "EventLog_*.txt")))]

@st.cache_data(show_spinner=False)
def parse_health(unit_path):
    path = os.path.join(unit_path, "system_health.txt")
    if not os.path.exists(path): return {}
    data = {}
    for line in read_text(path).splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            data[k.strip()] = v.strip()
    return data

def _decode_word_array(raw):
    """Decode a comma-separated list of 16-bit integers into an ASCII string."""
    try:
        chars = []
        for w in [int(x.strip()) for x in raw.split(',')]:
            hi, lo = (w >> 8) & 0xFF, w & 0xFF
            if 32 <= hi < 127: chars.append(chr(hi))
            if 32 <= lo < 127: chars.append(chr(lo))
        return ''.join(chars).strip() or None
    except:
        return None

def _fmt_fw(raw):
    """Format 'PC290300' → 'PC-29-03' matching HMI display style."""
    if not raw:
        return None
    m = re.match(r'^([A-Za-z]+)(\d{2})(\d{2})(\d{2})$', raw)
    if m:
        prefix, major, minor, patch = m.groups()
        return f"{prefix}-{major}-{minor}" if patch == "00" else f"{prefix}-{major}-{minor}-{patch}"
    return raw

@st.cache_data(show_spinner=False)
def parse_fw_sn(unit_path):
    log = os.path.join(unit_path, "verbose_logs", "cdu_app.log")
    if not os.path.exists(log):
        return None, None
    fw_pat = re.compile(r'FW Version retrieved successfully:\s*\[([^\]]+)\]')
    sn_pat = re.compile(r'Serial Number retrieved successfully:\s*\[([^\]]+)\]')
    fw_raw = sn_raw = None
    for line in read_tail(log, 200_000):
        if fw_raw is None:
            m = fw_pat.search(line)
            if m: fw_raw = m.group(1)
        if sn_raw is None:
            m = sn_pat.search(line)
            if m: sn_raw = m.group(1)
        if fw_raw and sn_raw:
            break
    fw = _fmt_fw(_decode_word_array(fw_raw)) if fw_raw else None
    sn = _decode_word_array(sn_raw) if sn_raw else None
    return fw, sn

@st.cache_data(show_spinner=False)
def load_configs(unit_path):
    cdir = os.path.join(unit_path, "config")
    out  = {}
    for fname in ["sensor_thresholds_config.json","scalar_definitions.json",
                  "agent_setting.json","event_config.json","system_metric.json"]:
        fp = os.path.join(cdir, fname)
        if os.path.exists(fp):
            try:
                with open(fp, "r", encoding="utf-8", errors="replace") as f:
                    out[fname] = json.load(f)
            except: pass
    return out

def _make_pid_fig(snap, ts_label):
    """Build an interactive Plotly P&ID schematic with live sensor values."""
    import math

    BLUE   = "#58a6ff"   # primary / facility cold water
    ORANGE = "#ffa657"   # secondary return (warm from servers)
    GREEN  = "#3fb950"   # secondary supply (cold to servers)
    PURPLE = "#bc8cff"   # internal CDU circuit (pump → manifold)
    FONT   = "Inter,'Segoe UI',system-ui,sans-serif"

    fig = go.Figure()
    fig.update_layout(
        plot_bgcolor="#0d1117", paper_bgcolor="#0d1117",
        margin=dict(l=10, r=10, t=44, b=10), height=580,
        xaxis=dict(range=[0, 10.5], showgrid=False, zeroline=False,
                   showticklabels=False, fixedrange=True),
        yaxis=dict(range=[0, 7.8], showgrid=False, zeroline=False,
                   showticklabels=False, fixedrange=True),
        title=dict(text=f"System P&ID  ·  Snapshot @ {ts_label}",
                   font=dict(color="#c9d1d9", size=13, family=FONT),
                   x=0.5, xanchor="center"),
        showlegend=False, dragmode=False,
    )

    def _g(col):
        v = snap.get(col)
        return None if (v is None or (isinstance(v, float) and math.isnan(v))) else float(v)

    def _v(col, fmt=".1f", unit=""):
        v = _g(col)
        return "—" if v is None else f"{format(v, fmt)}{unit}"

    def _pipe(x0, y0, x1, y1, c, w=3, dash="solid"):
        fig.add_shape(type="line", x0=x0, y0=y0, x1=x1, y1=y1,
                      line=dict(color=c, width=w, dash=dash))

    def _box(x0, y0, x1, y1, fc, sc, w=1.5):
        fig.add_shape(type="rect", x0=x0, y0=y0, x1=x1, y1=y1,
                      fillcolor=fc, line=dict(color=sc, width=w))

    def _circ(cx, cy, r, fc, sc, w=1.5):
        fig.add_shape(type="circle", x0=cx-r, y0=cy-r, x1=cx+r, y1=cy+r,
                      fillcolor=fc, line=dict(color=sc, width=w))

    def _ann(x, y, text, clr="#e6edf3", sz=10, anc="center", yanc="middle",
             bg=None, bclr=None, align="center"):
        kw = dict(x=x, y=y, text=text, showarrow=False,
                  font=dict(color=clr, size=sz, family=FONT),
                  xanchor=anc, yanchor=yanc, align=align)
        if bg:
            kw.update(bgcolor=bg, bordercolor=bclr or clr, borderwidth=1, borderpad=4)
        fig.add_annotation(**kw)

    def _flow_arrow(x, y, direction, color):
        """Place a directional arrow marker along a pipe to show flow direction."""
        symbols = {"left": "arrow-left", "right": "arrow-right",
                   "up": "arrow-up", "down": "arrow-down"}
        fig.add_trace(go.Scatter(
            x=[x], y=[y], mode="markers",
            marker=dict(symbol=symbols[direction], size=11, color=color,
                        line=dict(color=color, width=1)),
            showlegend=False, hoverinfo="skip",
        ))

    # ── PIPES ──────────────────────────────────────────────────────────────
    # Primary supply: facility chilled water enters from right → into HEX top
    _pipe(9.5, 6.3,  3.0, 6.3,  BLUE, 3)
    _pipe(3.0, 6.3,  3.0, 5.85, BLUE, 3)
    # Primary return: warm water exits HEX bottom → back to facility
    _pipe(3.0, 5.15, 3.0, 4.8,  BLUE, 3)
    _pipe(3.0, 4.8,  9.5, 4.8,  BLUE, 3)
    # Secondary return: hot water from servers enters from right → into HEX
    _pipe(9.5, 3.5,  3.0, 3.5,  ORANGE, 3)
    _pipe(3.0, 3.5,  3.0, 3.05, ORANGE, 3)
    # FIX: add the missing segment INSIDE the HEX (right wall → left wall)
    _pipe(3.0, 3.05, 1.5, 3.05, ORANGE, 2, "dot")
    # Secondary cooled water exits HEX left → into Tank
    _pipe(1.5, 3.05, 1.05, 3.05, ORANGE, 3)
    _pipe(1.05, 3.05, 1.05, 3.5, ORANGE, 3)
    # Tank bottom → pump inlet header (purple = internal CDU circuit)
    _pipe(0.65, 2.5,  0.65, 1.6, PURPLE, 3)
    _pipe(0.65, 1.6,  3.6,  1.6, PURPLE, 3)
    # Pump discharge stubs → outlet header
    for px in [1.4, 2.3, 3.2]:
        _pipe(px, 1.6, px, 2.15, PURPLE, 3)
    _pipe(1.4, 2.15, 4.0, 2.15, PURPLE, 3)
    _pipe(4.0, 2.15, 4.0, 1.85, PURPLE, 3)
    # FIX: start green supply pipe at manifold right edge (was 4.3, manifold ends at 4.25)
    _pipe(4.25, 2.0, 9.5, 2.0,  GREEN, 3)

    # ── FLOW DIRECTION ARROWS ──────────────────────────────────────────────
    _flow_arrow(6.5,  6.3,  "left",  BLUE)    # primary supply flows left
    _flow_arrow(6.5,  4.8,  "right", BLUE)    # primary return flows right
    _flow_arrow(8.5,  3.5,  "left",  ORANGE)  # secondary return flows left
    _flow_arrow(7.0,  2.0,  "right", GREEN)   # secondary supply flows right
    _flow_arrow(0.65, 2.1,  "down",  PURPLE)  # pump suction flows down
    _flow_arrow(2.8,  1.6,  "right", PURPLE)  # pump header flows right

    # ── PLATE HEAT EXCHANGER ───────────────────────────────────────────────
    _box(1.5, 2.8, 3.0, 6.5, "#060e1c", "#1f4f8c", w=2)
    for yy in [3.1, 3.4, 3.7, 4.0, 4.3, 4.6, 4.9, 5.2, 5.5, 5.8, 6.1, 6.4]:
        fig.add_shape(type="line", x0=1.5, y0=yy, x1=3.0, y1=yy,
                      line=dict(color="#0d2040", width=1))
    _ann(2.25, 4.65, "<b>Plate Heat<br>Exchanger</b>", "#79c0ff", 11)

    # Temperature difference across HEX — shows how much heat is being transferred
    pri_sup_t = _g("Primary Supply Temperature Reading")
    pri_ret_t = _g("Primary Return Temperature Reading")
    sec_sup_t = _g("Secondary Supply Temperature Reading")
    sec_ret_t = _g("Secondary Return Temperature Reading")
    if pri_sup_t is not None and pri_ret_t is not None:
        _ann(2.25, 5.45, f"Primary ΔT = {pri_ret_t - pri_sup_t:.1f}°C",
             BLUE, 9, bg="#0a0f1a", bclr=BLUE)
    if sec_sup_t is not None and sec_ret_t is not None:
        _ann(2.25, 3.55, f"Server ΔT = {sec_ret_t - sec_sup_t:.1f}°C",
             ORANGE, 9, bg="#1a0f0a", bclr=ORANGE)

    # ── TANK ──────────────────────────────────────────────────────────────
    _box(0.2, 2.5, 1.1, 4.5, "#061612", "#2d7a4f", w=2)
    res = _g("Reservoir Reading")
    if res is not None:
        wtop = 2.5 + (min(max(res, 0), 100) / 100) * 2.0
        _box(0.22, 2.5, 1.08, wtop, "rgba(0,100,220,0.30)", "rgba(0,0,0,0)", w=0)
        _ann(0.65, 2.7, f"{res:.0f}%", "#79c0ff", 10)
    _ann(0.65, 3.85, "Tank", "#e6edf3", 11)
    _ann(0.32, 4.35, "Full", "#6e7681", 9)
    _ann(0.32, 2.65, "Low", "#6e7681", 9)

    # ── MANIFOLD ──────────────────────────────────────────────────────────
    _box(3.85, 1.8, 4.25, 2.2, "#101a26", "#6e7681", w=1.5)
    _ann(4.05, 2.0, "Manifold", "#c9d1d9", 9)

    # ── FILTER ────────────────────────────────────────────────────────────
    _circ(7.2, 3.5, 0.40, "#18120a", ORANGE, 2)
    _ann(7.2, 3.5, "Filter", ORANGE, 10)

    # ── FLOW TRANSMITTERS ─────────────────────────────────────────────────
    _circ(8.3, 6.3, 0.36, "#0a1520", BLUE, 2)
    _ann(8.3, 6.3, "FT", BLUE, 10)
    _ann(8.3, 5.85, _v("Primary Flow Reading", ".1f", " LPM"), BLUE, 10)

    _circ(5.5, 3.5, 0.36, "#1a1208", ORANGE, 2)
    _ann(5.5, 3.5, "FT", ORANGE, 10)
    _ann(5.5, 3.05, _v("Secondary Flowrate Reading", ".1f", " LPM"), ORANGE, 10)

    # ── 2-WAY BYPASS VALVE (controls primary chilled water flow) ──────────
    v_bypass = _g("Valve Bypass Reading") or 0
    v_clr = "#3fb950" if v_bypass < 20 else ("#ffa657" if v_bypass < 60 else "#f85149")
    _box(6.45, 6.12, 7.0, 6.48, "#0d1117", v_clr, w=2)
    _ann(6.73, 6.3, "⧫", v_clr, 15)
    _ann(6.73, 5.82, f"Bypass {v_bypass:.0f}%", v_clr, 10)

    # ── PUMPS ─────────────────────────────────────────────────────────────
    for px, spd_col, alm_col, lbl in [
        (1.4, "Pump 1 Speed Reading", "Pump 1 Abnormal", "Pump 1"),
        (2.3, "Pump 2 Speed Reading", "Pump 2 Abnormal", "Pump 2"),
        (3.2, "Pump 3 Speed Reading", "Pump 3 Abnormal", "Pump 3"),
    ]:
        spd = _g(spd_col) or 0
        p_alm = snap.get(alm_col, 0) == 1
        p_clr = "#f85149" if p_alm else ("#3fb950" if spd > 100 else "#6e7681")
        status_txt = "FAULT" if p_alm else ("ON" if spd > 100 else "OFF")
        _circ(px, 1.88, 0.36, "#0a0f1a", p_clr, 2)
        _ann(px, 1.88, "▶", p_clr, 12)
        _ann(px, 2.40, lbl, "#c9d1d9", 9)
        _ann(px, 2.58, status_txt, p_clr, 8)
        _ann(px, 1.38, f"{spd:.0f} RPM", p_clr, 9)
        # Check valve mark
        _pipe(px - 0.12, 1.55, px + 0.12, 1.55, "#6e7681", 1)
        _pipe(px, 1.48, px, 1.62, "#6e7681", 1)

    # ── SENSOR VALUE BOXES (right side) ───────────────────────────────────
    def _t_color(t_val):
        """Color-code temperature: red = hot, orange = warm, blue = cool."""
        if t_val is None: return "#c9d1d9"
        if t_val > 45:    return "#f85149"
        if t_val > 35:    return "#ffa657"
        return "#79c0ff"

    def _sbox(y, arrow, label, t_col, p_col, pipe_clr):
        t_val = _g(t_col)
        t_str = "—" if t_val is None else f"{t_val:.1f}°C"
        t_clr = _t_color(t_val)
        p = _g(p_col)
        p_str = _v(p_col, ".1f", " kPa")
        p_clr = "#f85149" if (p is not None and p < 0) else \
                "#ffa657" if (p is not None and p < 50) else "#3fb950"
        _ann(9.55, y,
             f"<b>{arrow} {label}</b><br>"
             f"<span style='color:{t_clr}'>Temp: {t_str}</span><br>"
             f"<span style='color:{p_clr}'>Press: {p_str}</span>",
             "#e6edf3", 10, anc="left", yanc="middle",
             bg="#0d1320", bclr=pipe_clr)
        # connection nub aligning box to pipe
        _box(9.47, y - 0.17, 9.53, y + 0.17, pipe_clr, pipe_clr, w=0)

    # FIX: align sensor box y-coords to match actual pipe y-coords
    _sbox(6.3,  "▶", "PRIMARY IN",        "Primary Supply Temperature Reading",   "Primary Supply Pressure Reading",   BLUE)
    _sbox(4.8,  "◀", "PRIMARY OUT",       "Primary Return Temperature Reading",   "Primary Return Pressure Reading",   BLUE)
    _sbox(3.5,  "▶", "SERVER RETURN",     "Secondary Return Temperature Reading", "Secondary Return Pressure Reading", ORANGE)
    _sbox(2.0,  "◀", "SERVER SUPPLY",     "Secondary Supply Temperature Reading", "Secondary Supply Pressure Reading", GREEN)

    # ── DERIVED METRICS FOOTER ─────────────────────────────────────────────
    heat = _g("Heat Removal Reading")
    pwr  = _g("Total Power Consumption Reading")
    cop_str = f"{heat/pwr:.2f}" if (heat and pwr and pwr > 0) else "—"
    duty = _v("Pump Duty Reading", ".0f", "%")
    _ann(5.25, 1.1,
         f"Heat Removed: {_v('Heat Removal Reading','.0f',' W')}  |  "
         f"Total Power: {_v('Total Power Consumption Reading','.0f',' W')}  |  "
         f"COP (efficiency): {cop_str}  |  Pump Load: {duty}",
         "#bc8cff", 10, bg="#0d1117", bclr="#bc8cff")

    # ── LEGEND / ZONE LABELS ──────────────────────────────────────────────
    for (x, y, txt, c) in [
        (0.15, 7.62, "●  Blue  — Facility Chilled Water (Primary Circuit)",      BLUE),
        (0.15, 7.42, "●  Orange — Hot Return Water from Servers (Secondary)",     ORANGE),
        (0.15, 7.22, "●  Green — Cool Supply Water to Servers (Secondary)",       GREEN),
    ]:
        _ann(x, y, txt, c, 10, anc="left")

    return fig


def find_units(root):
    units = []
    for item in sorted(os.listdir(root)):
        full = os.path.join(root, item)
        if os.path.isdir(full) and os.path.isdir(os.path.join(full, "cdu")):
            units.append(full)
    return units

def filter_by_date(df, start, end):
    if df is None: return pd.DataFrame()
    if df.empty: return df
    if "Timestamp" not in df.columns: return df
    if start: df = df[df["Timestamp"] >= pd.Timestamp(start)]
    if end:   df = df[df["Timestamp"] <= pd.Timestamp(end) + pd.Timedelta(days=1)]
    return df if not df.empty else pd.DataFrame()

# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ CDU Log Dashboard")
    st.caption("Gen3 CDU CW — Log Visualizer")
    st.divider()

    st.subheader("📂 Load Unit Folder")
    mode = st.radio("Input mode", ["⬆️ Upload Archive", "📁 Local Path"], horizontal=True)

    unit_path = None

    # ── ARCHIVE UPLOAD MODE (ZIP / 7z) ────────────────────────────────────────
    if mode == "⬆️ Upload Archive":
        st.caption("Upload a ZIP or 7z of the unit folder (must contain cdu/, config/, verbose_logs/).")
        _accept_types = ["zip", "7z"] if _HAS_PY7ZR else ["zip"]
        uploaded = st.file_uploader("Drop ZIP or 7z here", type=_accept_types, label_visibility="collapsed")

        if uploaded:
            # Reuse same temp dir for same file (keyed by name+size)
            cache_key = f"zip_{uploaded.name}_{uploaded.size}"
            if st.session_state.get("zip_key") != cache_key:
                # Clean up previous temp dir
                old = st.session_state.get("zip_tmp")
                if old and os.path.isdir(old):
                    shutil.rmtree(old, ignore_errors=True)
                # Extract to new temp dir
                tmp = tempfile.mkdtemp(prefix="cdu_")
                _ext = os.path.splitext(uploaded.name)[1].lower()
                if _ext == ".7z":
                    if not _HAS_PY7ZR:
                        st.error("7z support requires py7zr — run: pip install py7zr")
                        st.stop()
                    import io
                    with py7zr.SevenZipFile(io.BytesIO(uploaded.read()), mode="r") as sz:
                        sz.extractall(path=tmp)
                else:
                    with zipfile.ZipFile(uploaded) as zf:
                        zf.extractall(tmp)
                st.session_state["zip_tmp"] = tmp
                st.session_state["zip_key"] = cache_key

            tmp = st.session_state["zip_tmp"]
            # Find the unit folder inside the zip
            sub_units = find_units(tmp)
            if sub_units:
                if len(sub_units) == 1:
                    unit_path = sub_units[0]
                    st.success(f"✓ Loaded: {os.path.basename(unit_path)}")
                else:
                    selected = st.selectbox("Select unit:", sub_units,
                                            format_func=os.path.basename)
                    unit_path = selected
            elif os.path.isdir(os.path.join(tmp, "cdu")):
                unit_path = tmp
                st.success(f"✓ Loaded: {uploaded.name}")
            else:
                # Look one level deeper
                for item in os.listdir(tmp):
                    candidate = os.path.join(tmp, item)
                    if os.path.isdir(candidate) and os.path.isdir(os.path.join(candidate, "cdu")):
                        unit_path = candidate
                        st.success(f"✓ Loaded: {item}")
                        break
                if not unit_path:
                    st.error("Archive doesn't contain a valid unit folder (no cdu/ subfolder found).")

    # ── LOCAL PATH MODE ───────────────────────────────────────────────────────
    else:
        st.caption("Paste the path to a CDU unit folder (contains cdu/, config/, verbose_logs/)")
        folder_path = st.text_input("Folder path",
                                    placeholder=r"e.g. C:\...\02242026 Logs\0511202500MS DH4 263")
        if folder_path and os.path.isdir(folder_path.strip()):
            fp = folder_path.strip()
            sub_units = find_units(fp)
            if sub_units:
                selected = st.selectbox("Unit folders detected:", sub_units,
                                        format_func=os.path.basename)
                unit_path = selected
            else:
                st.success("✓ This is the unit folder")
                unit_path = fp
        elif folder_path:
            st.error("Path not found")

    st.divider()
    st.subheader("🔍 Filter")
    date_range = st.date_input("Date range", value=[], help="Leave empty for all data")
    start_date = date_range[0] if len(date_range) > 0 else None
    end_date   = date_range[1] if len(date_range) > 1 else None

    resolution = st.slider("Chart resolution (points)", 500, 10000, 5000, 500,
                           help="Max data points plotted per chart. Higher = more detail but slower. "
                                "With 79k rows, default 2000 showed only every 39th row.")

    st.divider()

# ─────────────────────────────────────────────────────────────────────────────
# MAIN CONTENT
# ─────────────────────────────────────────────────────────────────────────────
if not unit_path:
    st.markdown("""
<div style="display:flex;flex-direction:column;align-items:center;justify-content:center;
            min-height:55vh;text-align:center;gap:1.25rem;">
  <div style="font-size:3.5rem;">⚙️</div>
  <div style="font-size:1.9rem;font-weight:700;color:#e6edf3;letter-spacing:-0.02em;">
    Gen3 CDU Log Dashboard
  </div>
  <div style="font-size:1rem;color:#8b949e;max-width:480px;line-height:1.6;">
    Upload a ZIP backup or paste the local folder path in the sidebar to start analysing CDU telemetry.
  </div>
  <div style="display:flex;gap:2rem;margin-top:0.5rem;">
    <div style="padding:1rem 1.5rem;background:rgba(22,27,34,0.8);border:1px solid #21262d;
                border-radius:10px;border-left:3px solid #58a6ff;text-align:left;min-width:180px;">
      <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.07em;color:#8b949e;margin-bottom:0.4rem;">Upload</div>
      <div style="font-size:0.92rem;color:#c9d1d9;">Zip the unit folder and drag it into the sidebar uploader.</div>
    </div>
    <div style="padding:1rem 1.5rem;background:rgba(22,27,34,0.8);border:1px solid #21262d;
                border-radius:10px;border-left:3px solid #3fb950;text-align:left;min-width:180px;">
      <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.07em;color:#8b949e;margin-bottom:0.4rem;">Local Path</div>
      <div style="font-size:0.92rem;color:#c9d1d9;">Paste the path to a folder containing <code>cdu/</code> and <code>config/</code>.</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)
    st.stop()

# Load all data (cached)
with st.spinner(f"Loading {os.path.basename(unit_path)}..."):
    sys_df  = load_system_logs(unit_path)
    alrt_df = parse_alert_log(unit_path)
    evnt_df = parse_event_log(unit_path)
    api_df  = parse_api_access(unit_path)
    verb_df = parse_verbose_logs(unit_path)
    configs = load_configs(unit_path)
    health  = parse_health(unit_path)
    evttxts = parse_event_txts(unit_path)
    fw_ver, unit_sn = parse_fw_sn(unit_path)

# Apply date filter
sys_df_f  = filter_by_date(sys_df,  start_date, end_date)
alrt_df_f = filter_by_date(alrt_df, start_date, end_date)
evnt_df_f = filter_by_date(evnt_df, start_date, end_date)
api_df_f  = filter_by_date(api_df,  start_date, end_date)
verb_df_f = filter_by_date(verb_df, start_date, end_date)

# Show loaded file inventory in sidebar
with st.sidebar:
    st.markdown('<p style="font-size:0.72rem;font-weight:700;text-transform:uppercase;'
                'letter-spacing:0.08em;color:#8b949e;margin-bottom:0.4rem;">📁 Loaded Files</p>',
                unsafe_allow_html=True)
    def _sb_stat(label, value, color="#58a6ff"):
        return (f'<div class="sidebar-stat">'
                f'<span class="sidebar-stat-label">{label}</span>'
                f'<span class="sidebar-stat-value" style="color:{color};">{value}</span>'
                f'</div>')
    st.markdown(
        _sb_stat("Sensor rows",   f"{len(sys_df):,}",   "#58a6ff") +
        _sb_stat("Alert events",  f"{len(alrt_df):,}",  "#f85149") +
        _sb_stat("Event entries", f"{len(evnt_df):,}",  "#e3b341") +
        _sb_stat("API requests",  f"{len(api_df):,}",   "#3fb950") +
        _sb_stat("Verbose rows",  f"{len(verb_df):,}",  "#bc8cff") +
        _sb_stat("Config files",  str(len(configs)),     "#ffa657") +
        _sb_stat("EventLog txts", str(len(evttxts)),    "#79c0ff"),
        unsafe_allow_html=True,
    )

# Unit header
unit_name = os.path.basename(unit_path)
_has_data   = not sys_df.empty
_running    = not sys_df_f.empty
_filtered   = _has_data and not _running   # data loaded but date filter wiped it
_badge_bg   = ("rgba(63,185,80,0.15)"  if _running else
               "rgba(210,153,34,0.15)" if _filtered else "rgba(248,81,73,0.15)")
_badge_bdr  = ("rgba(63,185,80,0.4)"   if _running else
               "rgba(210,153,34,0.4)"  if _filtered else "rgba(248,81,73,0.4)")
_badge_clr  = "#3fb950" if _running else "#d29922" if _filtered else "#f85149"
_badge_dot  = _badge_clr
_badge_lbl  = "RUNNING" if _running else "DATE FILTERED" if _filtered else "NO DATA"
st.markdown(f"""
<div style="display:flex;align-items:center;gap:14px;margin-bottom:0.2rem;flex-wrap:wrap;">
  <span style="font-size:1.55rem;font-weight:700;color:#e6edf3;letter-spacing:-0.02em;">
    ⚙️ {unit_name}
  </span>
  <span style="display:inline-flex;align-items:center;gap:5px;padding:3px 11px;
               border-radius:20px;font-size:0.7rem;font-weight:700;letter-spacing:0.06em;
               background:{_badge_bg};border:1px solid {_badge_bdr};color:{_badge_clr};">
    <span style="width:6px;height:6px;border-radius:50%;background:{_badge_dot};
                 display:inline-block;box-shadow:0 0 4px {_badge_dot};"></span>
    {_badge_lbl}
  </span>
</div>
<div style="font-size:0.8rem;color:#6e7681;margin-bottom:0.6rem;font-family:monospace;">
  {unit_path}
</div>
""", unsafe_allow_html=True)

# ── Device info card (mirrors HMI info screen) ────────────────────────────────
_health_sn_raw = health.get("Device SN") or None
# Firmware bug: some units write the IP address into the "Device SN" field — reject it
_is_ip = bool(_health_sn_raw and re.match(r'^\d{1,3}(\.\d{1,3}){3}$', _health_sn_raw.strip()))
_health_sn = None if _is_ip else _health_sn_raw
_unit_ip    = _health_sn_raw if _is_ip else None   # surface the IP separately if desired
_display_sn = _health_sn or unit_sn  # prefer system_health.txt, fall back to Modbus-decoded
if fw_ver or _display_sn:
    def _info_row(label, value, value_color="#c9d1d9"):
        return (f'<div style="display:flex;justify-content:space-between;align-items:baseline;'
                f'padding:5px 0;border-bottom:1px solid #21262d;">'
                f'<span style="font-size:0.78rem;color:#8b949e;white-space:nowrap;padding-right:1.5rem;">{label}</span>'
                f'<span style="font-size:0.82rem;font-weight:600;color:{value_color};font-family:monospace;">{value}</span>'
                f'</div>')
    rows = ""
    if fw_ver:
        rows += _info_row("Firmware version (Control Board)", fw_ver, "#79c0ff")
    if _display_sn:
        rows += _info_row("Serial Number", _display_sn, "#e6edf3")
    if unit_sn and _health_sn and unit_sn != _health_sn:
        rows += _info_row("Serial Number (Modbus)", unit_sn, "#8b949e")
    if _unit_ip:
        rows += _info_row("Unit IP Address", _unit_ip, "#8b949e")
    st.markdown(
        f'<div style="display:inline-block;min-width:380px;background:rgba(13,17,23,0.7);'
        f'border:1px solid #21262d;border-left:3px solid #30363d;border-radius:8px;'
        f'padding:10px 16px;margin-bottom:0.9rem;">'
        f'<div style="font-size:0.68rem;font-weight:700;text-transform:uppercase;letter-spacing:0.1em;'
        f'color:#6e7681;margin-bottom:6px;">&#9881; Device Info</div>'
        f'{rows}</div>',
        unsafe_allow_html=True,
    )

# ── KPI row ───────────────────────────────────────────────────────────────────
if not sys_df_f.empty:
    _ts_min = sys_df_f["Timestamp"].min()
    _ts_max_raw = sys_df_f["Timestamp"].max()
    # Cap max at report time (system_health) or now — guards against RTC-drifted future timestamps
    _report_time = pd.to_datetime(health.get("Report Time"), errors="coerce") if health.get("Report Time") else None
    _ts_ceiling  = _report_time if (_report_time is not None and not pd.isnull(_report_time)) else pd.Timestamp.now()
    _ts_max      = min(_ts_max_raw, _ts_ceiling)
    if _ts_max < _ts_min:
        _ts_max = _ts_max_raw  # fallback: don't produce negative duration
    dur_hrs = (_ts_max - _ts_min).total_seconds() / 3600
    dur_str = f"{dur_hrs/24:.1f} days" if dur_hrs >= 48 else f"{dur_hrs:.1f} hrs"
    start_ts = _ts_min.strftime("%b %d %Y\n%H:%M")   # pre-line renders \n as break

    _avg_cols = ["Total Power Consumption Reading", "Secondary Supply Temperature Reading",
                 "Valve Bypass Reading", "Primary Flow Reading", "Secondary Flowrate Reading"]
    _means = sys_df_f[[c for c in _avg_cols if c in sys_df_f.columns]].mean()  # single pass

    def col_avg(col):
        return float(_means[col]) if col in _means.index else None

    avg_p   = col_avg("Total Power Consumption Reading")
    avg_sec = col_avg("Secondary Supply Temperature Reading")
    avg_vb  = col_avg("Valve Bypass Reading")
    avg_pf  = col_avg("Primary Flow Reading")
    avg_sf  = col_avg("Secondary Flowrate Reading")

    kpi_items = [
        ("Running Since",          start_ts,                                          None,                                    None),
        ("Running Duration",       dur_str,                                           None,                                    None),
        ("Avg Power",              f"{avg_p:.0f} W"   if avg_p  is not None else "—", "Total Power Consumption Reading",       "#ffa657"),
        ("Avg Sec Supply Temp",    f"{avg_sec:.1f} °C" if avg_sec is not None else "—","Secondary Supply Temperature Reading", "#bc8cff"),
        ("Avg Valve Opening",      f"{avg_vb:.1f} %"  if avg_vb  is not None else "—","Valve Bypass Reading",                 "#58a6ff"),
        ("Avg Primary Flow",       f"{avg_pf:.1f} LPM" if avg_pf  is not None else "—","Primary Flow Reading",                "#3fb950"),
        ("Avg Secondary Flow",     f"{avg_sf:.1f} LPM" if avg_sf  is not None else "—","Secondary Flowrate Reading",           "#79c0ff"),
    ]

    if "kpi_selected" not in st.session_state:
        st.session_state["kpi_selected"] = None

    selected_col_key = st.session_state.get("kpi_selected")

    # Find which nth-child column is active so we can highlight it
    clickable_keys = [item[2] for item in kpi_items if item[2] is not None]
    active_col_nth = None
    if selected_col_key and selected_col_key in clickable_keys:
        active_col_nth = clickable_keys.index(selected_col_key) + 3  # 1-based; first 2 cols are non-clickable

    active_css = f"""
        .block-container .stHorizontalBlock:first-of-type
        .stColumn:nth-child({active_col_nth})
        button[data-testid="baseButton-secondary"] {{
            color: #58a6ff !important;
            border-bottom-color: #58a6ff !important;
        }}""" if active_col_nth else ""

    st.markdown(f"""<style>
    /* ── Clickable KPI value buttons (cols 3-7) ─────────────── */
    .block-container .stHorizontalBlock:first-of-type
    .stColumn:nth-child(n+3) button[data-testid="baseButton-secondary"] {{
        background: transparent !important;
        border: none !important;
        border-bottom: 2px solid transparent !important;
        color: #f0f6fc !important;
        font-size: 1.75rem !important;
        font-weight: 700 !important;
        letter-spacing: -0.02em !important;
        padding: 0.25rem 0 !important;
        text-align: left !important;
        cursor: pointer !important;
        line-height: 1.25 !important;
        box-shadow: none !important;
        border-radius: 0 !important;
        min-height: 2.6rem !important;
        width: 100% !important;
        display: block !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
        transition: color 0.15s, border-bottom-color 0.15s !important;
    }}
    .block-container .stHorizontalBlock:first-of-type
    .stColumn:nth-child(n+3) button[data-testid="baseButton-secondary"]:hover {{
        color: #58a6ff !important;
        border-bottom-color: #58a6ff !important;
        background: transparent !important;
    }}
    /* kpi-label is defined globally — no duplicate here */
    {active_css}
    </style>""", unsafe_allow_html=True)

    cols = st.columns(len(kpi_items))
    for i, (col_widget, (label, value, col_key, color)) in enumerate(zip(cols, kpi_items)):
        with col_widget:
            if col_key:
                # Render label as small text, value as a styled clickable button
                st.markdown(f'<p class="kpi-label">{label}</p>', unsafe_allow_html=True)
                if st.button(value, key=f"kpi_btn_{i}"):
                    st.session_state["kpi_selected"] = None if selected_col_key == col_key else col_key
                    st.rerun()
            else:
                st.metric(label, value)

    # Expandable chart for selected KPI
    if selected_col_key and selected_col_key in sys_df_f.columns:
        selected_col = selected_col_key
    else:
        selected_col = None
    if selected_col and selected_col in sys_df_f.columns:
        ds = downsample(sys_df_f, resolution)
        col_meta = {
            "Total Power Consumption Reading":      ("Power Consumption (W)", "#ffa657"),
            "Secondary Supply Temperature Reading": ("Secondary Supply Temp (°C)", "#bc8cff"),
            "Valve Bypass Reading":                 ("Valve Opening (%)", "#58a6ff"),
            "Primary Flow Reading":                 ("Primary Flow (LPM)", "#3fb950"),
            "Secondary Flowrate Reading":           ("Secondary Flow (LPM)", "#79c0ff"),
        }
        y_label, line_color = col_meta.get(selected_col, (short(selected_col), "#58a6ff"))
        mean_val = sys_df_f[selected_col].mean()

        fig_kpi = go.Figure()
        fig_kpi.add_trace(go.Scatter(
            x=ds["Timestamp"], y=ds[selected_col],
            fill="tozeroy", name=short(selected_col),
            line=dict(color=line_color, width=2)
        ))
        fig_kpi.add_hline(
            y=mean_val, line_dash="dash", line_color="#6e7681",
            annotation_text=f"Avg: {mean_val:.2f}",
            annotation_position="bottom right"
        )
        fig_kpi.update_layout(
            **CHART, title=f"{short(selected_col)} — full run",
            height=380, yaxis_title=y_label
        )
        add_rangeslider(fig_kpi)
        st.plotly_chart(fig_kpi, use_container_width=True, config=PLOTLY_CONFIG)

st.divider()

# ── TABS ──────────────────────────────────────────────────────────────────────
tabs = st.tabs(["📈 Sensors","🚨 Alarms","🌡 Temp & Flow",
                "⚙️ Pumps & Power","🌐 API Traffic",
                "📋 App Logs","📣 Alert / Events","🔧 Config & Health",
                "🔬 Thermal Analysis","📊 Custom Explorer"])

# ════════════════════════════════════════════════════════
# 📈 SENSORS
# ════════════════════════════════════════════════════════
with tabs[0]:
    if sys_df_f.empty:
        st.warning("No system_log data found.")
    else:
        st.markdown('<p class="section-header">Full run overview — all sensor channels</p>', unsafe_allow_html=True)
        ds = downsample(sys_df_f, resolution)
        fig = make_subplots(rows=5, cols=1, shared_xaxes=True, vertical_spacing=0.10,
            subplot_titles=("Temperature (°C)","Flow Rate (LPM)","Valve Bypass (%)","Pressure (kPa)","Power (W)"))
        for i, col in enumerate([c for c in TEMP_COLS[:4] if c in ds.columns]):
            fig.add_trace(go.Scatter(x=ds["Timestamp"], y=ds[col], name=short(col),
                line=dict(color=PAL[i], width=1.5)), row=1, col=1)
        for i, col in enumerate([c for c in FLOW_COLS if c in ds.columns]):
            fig.add_trace(go.Scatter(x=ds["Timestamp"], y=ds[col], name=short(col),
                line=dict(color=PAL[i+2], width=1.5)), row=2, col=1)
        if "Valve Bypass Reading" in ds.columns:
            fig.add_trace(go.Scatter(x=ds["Timestamp"], y=ds["Valve Bypass Reading"],
                fill="tozeroy", name="Valve Bypass %",
                line=dict(color="#ffa657", width=1.5)), row=3, col=1)
        for i, col in enumerate([c for c in PRES_COLS if c in ds.columns]):
            fig.add_trace(go.Scatter(x=ds["Timestamp"], y=ds[col], name=short(col),
                line=dict(color=PAL[i+4], width=1.5)), row=4, col=1)
        for i, col in enumerate([c for c in POWER_COLS[:2] if c in ds.columns]):
            fig.add_trace(go.Scatter(x=ds["Timestamp"], y=ds[col], name=short(col),
                line=dict(color=PAL[i+6], width=1.5),
                fill="tozeroy" if i == 0 else None), row=5, col=1)
        fig.update_xaxes(showticklabels=True, tickformat="%b %d\n%H:%M")
        fig.update_layout(**CHART, height=1400)
        fig.update_layout(margin=_MULTI_MARGIN, legend=_MULTI_LEGEND)
        style_fig(fig)
        add_rangeselector(fig, row=1, col=1)   # time-range buttons; drag-box to zoom; dbl-click resets
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
        step = max(1, len(sys_df_f) // resolution)
        st.caption(f"Showing {len(ds):,} of {len(sys_df_f):,} rows (every {step}{'st' if step==1 else 'th'} row). "
                   f"Increase 'Chart resolution' in the sidebar to see more detail.")

# ════════════════════════════════════════════════════════
# 🚨 ALARMS
# ════════════════════════════════════════════════════════
with tabs[1]:
    if sys_df_f.empty:
        st.warning("No system_log data found.")
    else:
        st.markdown('<p class="section-header">Alarm event counts & timeline heatmap</p>', unsafe_allow_html=True)
        alarms = active_alarms(sys_df_f)
        if not alarms:
            st.success("✅ No alarms detected.")
        else:
            total_rows = len(sys_df_f)
            s_al  = sorted(alarms, key=lambda x: x[1], reverse=True)
            vals  = [v for _, v in s_al]
            pcts  = [v / total_rows * 100 for v in vals]   # % of samples active
            names = [short(k) for k, _ in s_al]

            # Severity based on % of samples the alarm was active (not raw count)
            # ≥ 50 % of samples  → Critical (persistent fault)
            # ≥  5 % of samples  → Warning  (intermittent)
            # <  5 %             → Minor    (occasional)
            def sev_color(pct):
                return "#f85149" if pct >= 50 else "#d29922" if pct >= 5 else "#58a6ff"

            col1, col2 = st.columns(2)
            with col1:
                bar = go.Figure(go.Bar(
                    x=pcts, y=names, orientation="h",
                    marker_color=[sev_color(p) for p in pcts],
                    text=[f"{p:.1f}% ({v:,})" for p, v in zip(pcts, vals)],
                    textposition="outside", cliponaxis=False,
                    customdata=vals,
                    hovertemplate="<b>%{y}</b><br>%{x:.2f}% of samples<br>Count: %{customdata:,}<extra></extra>",
                ))
                bar.update_layout(**CHART, title=f"Alarm Active-Sample Rate (% of {total_rows:,} rows)",
                                  height=max(300, len(s_al)*40), xaxis_title="% of samples")
                bar.update_layout(margin=dict(l=60, r=130, t=52, b=44))
                bar.update_yaxes(automargin=True)
                style_fig(bar)
                st.plotly_chart(bar, use_container_width=True, config=PLOTLY_CONFIG)

            with col2:
                ac  = [k for k, _ in s_al]
                dfa = sys_df_f[["Timestamp"]+ac].set_index("Timestamp").resample("1h").mean().reset_index()
                heat = go.Figure(go.Heatmap(
                    z=dfa[ac].T.values, x=dfa["Timestamp"], y=[short(c) for c in ac],
                    colorscale=[[0,"#161b22"],[0.01,"#d29922"],[1,"#f85149"]],
                    zmin=0, zmax=1, showscale=False,
                    hovertemplate="%{y}<br>%{x}<br>Active rate: %{z:.0%}<extra></extra>",
                ))
                heat.update_layout(**CHART, title="Alarm Active Rate — Hourly Heatmap (0=off, 1=on)",
                                   height=max(240, len(ac)*32))
                style_fig(heat)
                st.plotly_chart(heat, use_container_width=True, config=PLOTLY_CONFIG)

            tbl_data = [{"Alarm": short(k), "Count": f"{v:,}", "% of Samples": f"{p:.1f}%",
                         "Severity": "Critical" if p>=50 else "Warning" if p>=5 else "Minor"}
                        for (k, v), p in zip(s_al, pcts)]
            st.dataframe(pd.DataFrame(tbl_data), use_container_width=True, hide_index=True)

# ════════════════════════════════════════════════════════
# 🌡 TEMP & FLOW
# ════════════════════════════════════════════════════════
with tabs[2]:
    if sys_df_f.empty:
        st.warning("No system_log data found.")
    else:
        ds = downsample(sys_df_f, resolution)
        fig = make_subplots(
            rows=5, cols=1, shared_xaxes=True, vertical_spacing=0.08,
            subplot_titles=(
                "Temperature (°C)",
                "Primary & Secondary Supply Temp vs Valve Bypass %",
                "Flow Rate (LPM)",
                "Primary Flow vs Valve Bypass — Primary Water Sufficiency",
                "Secondary Loop Pressure (kPa) — Negative = Air / Cavitation Risk",
            ),
            specs=[
                [{"secondary_y": False}],
                [{"secondary_y": True}],
                [{"secondary_y": False}],
                [{"secondary_y": True}],
                [{"secondary_y": False}],
            ],
        )
        # Row 1 — all temperatures
        for i, col in enumerate([c for c in TEMP_COLS if c in ds.columns]):
            fig.add_trace(go.Scatter(x=ds["Timestamp"], y=ds[col], name=short(col),
                line=dict(color=PAL[i], width=1.5)), row=1, col=1)
        # Row 2 — Primary Supply Temp + Secondary Supply Temp (left °C axis) + Valve Bypass % (right axis)
        if "Primary Supply Temperature Reading" in ds.columns:
            fig.add_trace(go.Scatter(x=ds["Timestamp"], y=ds["Primary Supply Temperature Reading"],
                name="Primary Supply Temp", line=dict(color="#58a6ff", width=2)),
                row=2, col=1, secondary_y=False)
        if "Secondary Supply Temperature Reading" in ds.columns:
            fig.add_trace(go.Scatter(x=ds["Timestamp"], y=ds["Secondary Supply Temperature Reading"],
                name="Secondary Supply Temp", line=dict(color="#3fb950", width=2)),
                row=2, col=1, secondary_y=False)
        if "Valve Bypass Reading" in ds.columns:
            fig.add_trace(go.Scatter(x=ds["Timestamp"], y=ds["Valve Bypass Reading"],
                fill="tozeroy", name="Valve Bypass %", opacity=0.35,
                line=dict(color="#ffa657", width=1.5)),
                row=2, col=1, secondary_y=True)
        fig.update_yaxes(title_text="Temp (°C)", row=2, col=1, secondary_y=False)
        fig.update_yaxes(title_text="Bypass (%)", row=2, col=1, secondary_y=True,
                         range=[0, 105], showgrid=False)
        # Row 3 — flow rate
        for i, col in enumerate([c for c in FLOW_COLS if c in ds.columns]):
            fig.add_trace(go.Scatter(x=ds["Timestamp"], y=ds[col], name=short(col),
                line=dict(color=PAL[i+4], width=1.5)), row=3, col=1)
        # Row 4 — Primary Flow (left) vs Valve Bypass % (right): primary water sufficiency check
        # High bypass + low primary flow → insufficient primary water supply
        if "Primary Flow Reading" in ds.columns:
            fig.add_trace(go.Scatter(x=ds["Timestamp"], y=ds["Primary Flow Reading"],
                name="Primary Flow (LPM)", line=dict(color="#3fb950", width=2.5)),
                row=4, col=1, secondary_y=False)
        if "Valve Bypass Reading" in ds.columns:
            fig.add_trace(go.Scatter(x=ds["Timestamp"], y=ds["Valve Bypass Reading"],
                fill="tozeroy", name="Valve Bypass % (sufficiency)", opacity=0.40,
                line=dict(color="#ffa657", width=2)),
                row=4, col=1, secondary_y=True)
        fig.update_yaxes(title_text="Primary Flow (LPM)", row=4, col=1, secondary_y=False)
        fig.update_yaxes(title_text="Bypass (%)", row=4, col=1, secondary_y=True,
                         range=[0, 105], showgrid=False)
        # Row 5 — Secondary Supply & Return Pressure with zero reference line
        _sec_pres_colors = {"Secondary Supply Pressure Reading": "#58a6ff",
                            "Secondary Return Pressure Reading": "#ffa657"}
        for col, clr in _sec_pres_colors.items():
            if col in ds.columns:
                fig.add_trace(go.Scatter(x=ds["Timestamp"], y=ds[col], name=short(col),
                    line=dict(color=clr, width=2)), row=5, col=1)
        # Zero reference line — values below this indicate negative/sub-atmospheric pressure
        fig.add_hline(y=0, line=dict(color="#f85149", width=1.5, dash="dash"),
                      annotation_text="0 kPa (atmospheric)", annotation_font_color="#f85149",
                      annotation_position="bottom right", row=5, col=1)
        fig.update_yaxes(title_text="Pressure (kPa)", row=5, col=1)
        fig.update_xaxes(showticklabels=True, tickformat="%b %d\n%H:%M")
        fig.update_layout(**CHART, height=1500)
        fig.update_layout(margin=_MULTI_MARGIN, legend=_MULTI_LEGEND)
        style_fig(fig)
        add_rangeselector(fig, row=1, col=1)
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
        st.caption("Row 4 — Sustained high bypass (%) with low primary flow (LPM) indicates insufficient "
                   "primary water supply. | Row 5 — Secondary return pressure below 0 kPa indicates "
                   "sub-atmospheric (negative) pressure: possible air entrapment or cavitation risk.")

# ════════════════════════════════════════════════════════
# ⚙️ PUMPS & POWER
# ════════════════════════════════════════════════════════
with tabs[3]:
    if sys_df_f.empty:
        st.warning("No system_log data found.")
    else:
        ds = downsample(sys_df_f, resolution)
        fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.11,
            subplot_titles=("Pump Speed (RPM)","Duty Cycle (%)","Power & Heat (W)","Valve Bypass (%)"))
        for i, col in enumerate([c for c in PUMP_COLS[:3] if c in ds.columns]):
            fig.add_trace(go.Scatter(x=ds["Timestamp"], y=ds[col], name=short(col),
                line=dict(color=PAL[i], width=1.5)), row=1, col=1)
        for i, col in enumerate([c for c in ["Pump Duty Reading","Fan Duty Reading"] if c in ds.columns]):
            fig.add_trace(go.Scatter(x=ds["Timestamp"], y=ds[col], fill="tozeroy",
                name=short(col), line=dict(color=PAL[i+3], width=1.5)), row=2, col=1)
        for i, col in enumerate([c for c in POWER_COLS if c in ds.columns]):
            fig.add_trace(go.Scatter(x=ds["Timestamp"], y=ds[col], name=short(col),
                line=dict(color=PAL[i+5], width=1.5)), row=3, col=1)
        if "Valve Bypass Reading" in ds.columns:
            fig.add_trace(go.Scatter(x=ds["Timestamp"], y=ds["Valve Bypass Reading"],
                fill="tozeroy", name="Valve Bypass %",
                line=dict(color="#ffa657", width=2)), row=4, col=1)
        fig.update_xaxes(showticklabels=True, tickformat="%b %d\n%H:%M")
        fig.update_layout(**CHART, height=1150)
        fig.update_layout(margin=_MULTI_MARGIN, legend=_MULTI_LEGEND)
        style_fig(fig)
        add_rangeselector(fig, row=1, col=1)
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

# ════════════════════════════════════════════════════════
# 🌐 API TRAFFIC
# ════════════════════════════════════════════════════════
with tabs[4]:
    if api_df_f.empty:
        st.warning("No API access log data found.")
    else:
        vol = api_df_f.set_index("Timestamp").resample("15min").size().reset_index(name="count")
        fig_vol = go.Figure(go.Scatter(x=vol["Timestamp"], y=vol["count"],
            fill="tozeroy", name="Requests/15min", line=dict(color="#3fb950", width=1.5)))
        fig_vol.update_layout(**CHART, title="API Request Volume (per 15 min)", height=300)
        style_fig(fig_vol)
        add_rangeselector(fig_vol, row=None)   # time-range buttons for the volume chart
        add_rangeslider(fig_vol)               # drag-handle at the bottom

        ds_api = downsample(api_df_f, 1500)
        fig_rt = go.Figure()
        fig_rt.add_trace(go.Scatter(x=ds_api["Timestamp"], y=ds_api["ResponseMs"], mode="markers",
            name="Response Time",
            marker=dict(color=["#f85149" if s >= 400 else "#3fb950" for s in ds_api["Status"]],
                        size=3, opacity=0.6)))
        fig_rt.update_layout(**CHART, title="API Response Time (ms) — 🔴 = error", height=300)
        style_fig(fig_rt)
        add_rangeselector(fig_rt, row=None)

        col1, col2 = st.columns(2)
        with col1: st.plotly_chart(fig_vol, use_container_width=True, config=PLOTLY_CONFIG)
        with col2: st.plotly_chart(fig_rt,  use_container_width=True, config=PLOTLY_CONFIG)

        st_counts = api_df_f["Status"].value_counts().sort_index()
        def st_color(s): return "#3fb950" if s < 300 else "#d29922" if s < 400 else "#f85149"
        fig_st = go.Figure(go.Bar(x=[str(s) for s in st_counts.index], y=st_counts.values,
            marker_color=[st_color(s) for s in st_counts.index],
            text=st_counts.values, textposition="outside", cliponaxis=False))
        fig_st.update_layout(**CHART, title="HTTP Status Codes", height=280, showlegend=False)
        fig_st.update_layout(margin=dict(l=60, r=56, t=52, b=60))
        fig_st.update_xaxes(automargin=True)
        style_fig(fig_st)

        ep = api_df_f["Endpoint"].value_counts().head(15)
        fig_ep = go.Figure(go.Bar(x=ep.values, y=[e[:55] for e in ep.index], orientation="h",
            marker_color="#58a6ff", text=ep.values, textposition="outside", cliponaxis=False))
        fig_ep.update_layout(**CHART, title="Top 15 Endpoints",
                              height=max(300, len(ep)*32), showlegend=False)
        fig_ep.update_layout(margin=dict(l=60, r=80, t=52, b=44))
        fig_ep.update_yaxes(automargin=True)
        style_fig(fig_ep)

        client_counts = api_df_f["Client"].value_counts()
        fig_cl = go.Figure(go.Pie(
            labels=client_counts.index.tolist(),
            values=client_counts.values.tolist(),
            marker_colors=PAL, hole=0.42))
        fig_cl.update_layout(**CHART, title="Requests by Client IP", height=300)

        col3, col4 = st.columns(2)
        with col3: st.plotly_chart(fig_st, use_container_width=True, config=PLOTLY_CONFIG)
        with col4: st.plotly_chart(fig_cl, use_container_width=True, config=PLOTLY_CONFIG)

        st.plotly_chart(fig_ep, use_container_width=True, config=PLOTLY_CONFIG)

        errors_df = api_df_f[api_df_f["Status"] >= 400].sort_values("Timestamp", ascending=False).head(100)
        if not errors_df.empty:
            st.markdown(f"**{len(errors_df)} API error responses (4xx/5xx)**")
            st.dataframe(errors_df[["Timestamp","Method","Endpoint","Status","ResponseMs","Client"]],
                         use_container_width=True, hide_index=True)

# ════════════════════════════════════════════════════════
# 📋 APP LOGS
# ════════════════════════════════════════════════════════
with tabs[5]:
    if verb_df_f.empty:
        st.warning("No verbose log data found.")
    else:
        pivot   = verb_df_f.groupby(["Log","Level"]).size().unstack(fill_value=0)
        lvl_c   = [c for c in ["ERROR","WARNING","WARN","INFO","DEBUG"] if c in pivot.columns]
        clr_map = {"ERROR":"#f85149","WARNING":"#d29922","WARN":"#d29922","INFO":"#58a6ff","DEBUG":"#6e7681"}
        fig_lv  = go.Figure()
        for lvl in lvl_c:
            fig_lv.add_trace(go.Bar(name=lvl, x=pivot.index.tolist(), y=pivot[lvl].tolist(),
                marker_color=clr_map.get(lvl, "#bc8cff")))
        fig_lv.update_layout(**CHART, title="Log Level by Service", barmode="stack", height=340)
        style_fig(fig_lv)
        st.plotly_chart(fig_lv, use_container_width=True, config=PLOTLY_CONFIG)

        errors = verb_df_f[verb_df_f["Level"].isin(["ERROR","CRITICAL","FATAL"])].copy()
        if not errors.empty:
            ev = errors.set_index("Timestamp").resample("1h").size().reset_index(name="errors")
            fe = go.Figure(go.Bar(x=ev["Timestamp"], y=ev["errors"],
                name="Errors/hr", marker_color="#f85149"))
            fe.update_layout(**CHART, title="Error Rate Over Time", height=250)
            style_fig(fe)
            st.plotly_chart(fe, use_container_width=True, config=PLOTLY_CONFIG)

            st.markdown(f"**{len(errors)} ERROR entries (max 250 shown)**")
            st.dataframe(errors[["Timestamp","Log","Level","Message"]].head(250),
                         use_container_width=True, hide_index=True)

# ════════════════════════════════════════════════════════
# 📣 ALERT / EVENTS
# ════════════════════════════════════════════════════════
with tabs[6]:
    if not alrt_df_f.empty:
        alarms_list = alrt_df_f["Alarm"].unique().tolist()
        fig_tl = go.Figure()
        for i, alarm in enumerate(alarms_list):
            sub = alrt_df_f[alrt_df_f["Alarm"] == alarm]
            asr = sub[sub["State"] == "asserted"]
            das = sub[sub["State"] == "deasserted"]
            fig_tl.add_trace(go.Scatter(x=asr["Timestamp"], y=[alarm]*len(asr), mode="markers",
                name="asserted", marker=dict(symbol="triangle-up", color="#f85149", size=10),
                showlegend=(i == 0)))
            fig_tl.add_trace(go.Scatter(x=das["Timestamp"], y=[alarm]*len(das), mode="markers",
                name="deasserted", marker=dict(symbol="triangle-down", color="#3fb950", size=10),
                showlegend=(i == 0)))
        fig_tl.update_layout(**CHART, title="Alert Timeline — ▲ Asserted  ▼ Deasserted",
                              height=max(320, len(alarms_list)*50))
        style_fig(fig_tl)
        add_rangeselector(fig_tl, row=None)
        st.plotly_chart(fig_tl, use_container_width=True, config=PLOTLY_CONFIG)

        cnt = alrt_df_f[alrt_df_f["State"] == "asserted"]["Alarm"].value_counts()
        col1, col2 = st.columns(2)
        with col1:
            fig_cnt = go.Figure(go.Bar(x=cnt.values, y=cnt.index.tolist(), orientation="h",
                marker_color="#f85149", text=cnt.values, textposition="outside",
                cliponaxis=False))
            fig_cnt.update_layout(**CHART, title="Alert Occurrences",
                                   height=max(250, len(cnt)*38), showlegend=False)
            fig_cnt.update_layout(margin=dict(l=60, r=80, t=52, b=44))
            fig_cnt.update_yaxes(automargin=True)
            st.plotly_chart(fig_cnt, use_container_width=True, config=PLOTLY_CONFIG)

        with col2:
            st.markdown("**Assert → Deassert Durations**")
            # Vectorized pairing: for each deasserted event find the nearest prior asserted event
            # merge_asof requires each df sorted by the join key (time), not multi-column
            _asr = (alrt_df_f[alrt_df_f["State"] == "asserted"]
                    .rename(columns={"Timestamp": "Asserted At"})[["Alarm","Asserted At"]]
                    .sort_values("Asserted At").reset_index(drop=True))
            _das = (alrt_df_f[alrt_df_f["State"] == "deasserted"]
                    .rename(columns={"Timestamp": "Deasserted At"})[["Alarm","Deasserted At"]]
                    .sort_values("Deasserted At").reset_index(drop=True))
            # left_on/right_on because the key column has different names in each df
            _paired = pd.merge_asof(_das, _asr,
                                    left_on="Deasserted At", right_on="Asserted At",
                                    by="Alarm", direction="backward")
            _paired = _paired.dropna(subset=["Asserted At"])
            _paired = _paired[_paired["Asserted At"] <= _paired["Deasserted At"]]
            if not _paired.empty:
                secs = (_paired["Deasserted At"] - _paired["Asserted At"]).dt.total_seconds()
                _paired["Duration"] = secs.apply(
                    lambda s: f"{int(s//60)}m {int(s%60)}s" if s < 3600 else f"{s/3600:.1f}h")
                _paired["Asserted At"]   = _paired["Asserted At"].dt.strftime("%Y-%m-%d %H:%M:%S")
                _paired["Deasserted At"] = _paired["Deasserted At"].dt.strftime("%Y-%m-%d %H:%M:%S")
                st.dataframe(_paired[["Asserted At","Alarm","Deasserted At","Duration"]],
                             use_container_width=True, hide_index=True)

        st.markdown(f"**Full alert log — {len(alrt_df_f)} entries**")
        st.dataframe(alrt_df_f, use_container_width=True, hide_index=True)

    if not evnt_df_f.empty:
        st.markdown(f"**event_log_1 — {len(evnt_df_f)} entries**")
        st.dataframe(evnt_df_f, use_container_width=True, hide_index=True)

    if evttxts:
        st.subheader("EventLog_*.txt snapshots")
        for e in evttxts:
            with st.expander(e["file"]):
                st.code(e["content"][:1500])

    if alrt_df_f.empty and evnt_df_f.empty and not evttxts:
        st.warning("No alert/event data found.")

# ════════════════════════════════════════════════════════
# 🔧 CONFIG & HEALTH
# ════════════════════════════════════════════════════════
with tabs[7]:
    if health:
        st.subheader("system_health.txt")
        st.dataframe(pd.DataFrame(list(health.items()), columns=["Key","Value"]),
                     use_container_width=True, hide_index=True)

    if configs:
        for fname, cfg in configs.items():
            with st.expander(fname):
                st.json(cfg)

    if not health and not configs:
        st.warning("No config/health data found.")

# ════════════════════════════════════════════════════════
# 🔬 THERMAL ANALYSIS
# ════════════════════════════════════════════════════════
with tabs[8]:
    if sys_df_f.empty:
        st.warning("No system_log data found.")
    else:
        ds = downsample(sys_df_f, resolution).copy()

        # ── P&ID SNAPSHOT ─────────────────────────────────────────────────────
        st.markdown('<p class="section-header">System Overview — P&ID Live Snapshot</p>',
                    unsafe_allow_html=True)
        _pid_max = len(sys_df_f) - 1
        _pid_idx = st.slider(
            "Snapshot position",
            min_value=0, max_value=_pid_max, value=_pid_max,
            help="Drag to replay any point in the log. Default = latest.",
            label_visibility="collapsed",
        )
        _snap_row  = sys_df_f.iloc[_pid_idx]
        _snap_ts   = str(_snap_row["Timestamp"])[:19]
        _snap_dict = _snap_row.to_dict()
        st.caption(f"Snapshot @ **{_snap_ts}**  ·  row {_pid_idx+1:,} of {_pid_max+1:,}")
        st.plotly_chart(
            _make_pid_fig(_snap_dict, _snap_ts),
            use_container_width=True,
            config={**PLOTLY_CONFIG, "staticPlot": True},
        )

        st.divider()

        # ── Compute derived thermal metrics ──────────────────────────────────
        def _safe_col(df, col):
            return df[col] if col in df.columns else pd.Series(float("nan"), index=df.index)

        sec_ret_t  = _safe_col(ds, "Secondary Return Temperature Reading")
        sec_sup_t  = _safe_col(ds, "Secondary Supply Temperature Reading")
        pri_ret_t  = _safe_col(ds, "Primary Return Temperature Reading")
        pri_sup_t  = _safe_col(ds, "Primary Supply Temperature Reading")
        sec_sup_p  = _safe_col(ds, "Secondary Supply Pressure Reading")
        sec_ret_p  = _safe_col(ds, "Secondary Return Pressure Reading")
        dew        = _safe_col(ds, "Dew Point Reading")
        heat_rem   = _safe_col(ds, "Heat Removal Reading")
        total_pwr  = _safe_col(ds, "Total Power Consumption Reading").replace(0, float("nan"))
        valve      = _safe_col(ds, "Valve Bypass Reading")
        sec_flow   = _safe_col(ds, "Secondary Flowrate Reading")

        ds["ΔT Secondary (°C)"]      = sec_ret_t - sec_sup_t          # heat absorbed from servers
        ds["ΔT Primary (°C)"]        = pri_ret_t - pri_sup_t          # heat rejected to facility
        ds["HEX Approach Temp (°C)"] = pri_ret_t - sec_sup_t          # HEX effectiveness — lower = better
        ds["COP"]                    = heat_rem / total_pwr            # system efficiency
        ds["Dew Point Margin (°C)"]  = sec_sup_t - dew                # <0 = condensation risk
        ds["Secondary ΔP (kPa)"]     = sec_sup_p - sec_ret_p          # differential pressure across secondary loop

        # ── KPI cards ────────────────────────────────────────────────────────
        _mean = lambda s: round(s.dropna().mean(), 2) if not s.dropna().empty else None
        _min  = lambda s: round(s.dropna().min(),  2) if not s.dropna().empty else None

        kc = st.columns(6)
        _kpi_defs = [
            ("ΔT Secondary",      ds["ΔT Secondary (°C)"],      "°C",  "#58a6ff",  "Heat absorbed by CDU from servers"),
            ("ΔT Primary",        ds["ΔT Primary (°C)"],        "°C",  "#3fb950",  "Heat rejected to facility chilled water"),
            ("HEX Approach Temp", ds["HEX Approach Temp (°C)"], "°C",  "#ffa657",  "Lower = better HEX performance; rising = fouling"),
            ("Avg COP",           ds["COP"],                    "",    "#bc8cff",  "Heat Removal / Power — higher = more efficient"),
            ("Min Dew Margin",    ds["Dew Point Margin (°C)"],  "°C",  "#f85149" if (_min(ds["Dew Point Margin (°C)"]) or 5) < 2 else "#e3b341",
                                                                                   "Supply temp − Dew point; <0 = condensation risk"),
            ("Avg Secondary ΔP",  ds["Secondary ΔP (kPa)"],     "kPa", "#79c0ff",  "Supply − Return pressure; low/neg = air risk"),
        ]
        for col_ui, (label, series, unit, clr, tip) in zip(kc, _kpi_defs):
            val = _mean(series) if label != "Min Dew Margin" else _min(series)
            display = f"{val} {unit}" if val is not None else "N/A"
            col_ui.metric(label, display, help=tip)

        st.divider()

        # ── Chart 1: Delta-T analysis ─────────────────────────────────────────
        st.markdown('<p class="section-header">ΔT Analysis — Heat Transfer Performance</p>',
                    unsafe_allow_html=True)
        fig1 = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.10,
            subplot_titles=("ΔT Secondary & Primary (°C) — Heat Balance",
                            "HEX Approach Temperature (°C) — Fouling Indicator"))
        for col, clr, dash in [
            ("ΔT Secondary (°C)", "#58a6ff", "solid"),
            ("ΔT Primary (°C)",   "#3fb950", "solid"),
        ]:
            fig1.add_trace(go.Scatter(x=ds["Timestamp"], y=ds[col], name=col,
                line=dict(color=clr, width=2, dash=dash)), row=1, col=1)
        fig1.add_hline(y=0, line=dict(color="#f85149", width=1, dash="dot"), row=1, col=1)
        fig1.add_trace(go.Scatter(x=ds["Timestamp"], y=ds["HEX Approach Temp (°C)"],
            name="HEX Approach Temp", line=dict(color="#ffa657", width=2)), row=2, col=1)
        fig1.update_yaxes(title_text="ΔT (°C)", row=1, col=1)
        fig1.update_yaxes(title_text="Approach Temp (°C)", row=2, col=1)
        fig1.update_xaxes(showticklabels=True, tickformat="%b %d\n%H:%M")
        fig1.update_layout(**CHART, height=600)
        fig1.update_layout(margin=_MULTI_MARGIN, legend=_MULTI_LEGEND)
        style_fig(fig1)
        st.plotly_chart(fig1, use_container_width=True, config=PLOTLY_CONFIG)
        st.caption("ΔT Secondary = server heat load absorbed. ΔT Primary = facility heat rejection. "
                   "HEX Approach rising over time signals fouling or scaling in the heat exchanger.")

        st.divider()

        # ── Chart 2: COP + Secondary ΔP ──────────────────────────────────────
        st.markdown('<p class="section-header">System Efficiency & Hydraulic Health</p>',
                    unsafe_allow_html=True)
        fig2 = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.10,
            subplot_titles=("COP — Coefficient of Performance (Heat Removal / Power In)",
                            "Secondary Loop ΔP (kPa) — Hydraulic Balance & Air Detection"))
        fig2.add_trace(go.Scatter(x=ds["Timestamp"], y=ds["COP"],
            name="COP", line=dict(color="#bc8cff", width=2)), row=1, col=1)
        fig2.add_hline(y=1, line=dict(color="#f85149", width=1, dash="dot"),
                       annotation_text="COP = 1 (break-even)", annotation_font_color="#f85149",
                       annotation_position="bottom right", row=1, col=1)
        fig2.add_trace(go.Scatter(x=ds["Timestamp"], y=ds["Secondary ΔP (kPa)"],
            name="Secondary ΔP", line=dict(color="#79c0ff", width=2)), row=2, col=1)
        fig2.add_hline(y=0, line=dict(color="#f85149", width=1.5, dash="dash"),
                       annotation_text="0 kPa — below = air / cavitation risk",
                       annotation_font_color="#f85149", annotation_position="bottom right",
                       row=2, col=1)
        fig2.update_yaxes(title_text="COP", row=1, col=1)
        fig2.update_yaxes(title_text="ΔP (kPa)", row=2, col=1)
        fig2.update_xaxes(showticklabels=True, tickformat="%b %d\n%H:%M")
        fig2.update_layout(**CHART, height=600)
        fig2.update_layout(margin=_MULTI_MARGIN, legend=_MULTI_LEGEND)
        style_fig(fig2)
        st.plotly_chart(fig2, use_container_width=True, config=PLOTLY_CONFIG)
        st.caption("COP below 1 means the CDU is consuming more power than it is removing heat — investigate pump/fan load. "
                   "Secondary ΔP near 0 or negative indicates low system pressure: possible air entrapment, pump cavitation, "
                   "or insufficient make-up pressure.")

        st.divider()

        # ── Chart 3: Dew Point Margin + PID response ─────────────────────────
        st.markdown('<p class="section-header">Condensation Risk & PID Control Response</p>',
                    unsafe_allow_html=True)
        fig3 = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.10,
            specs=[[{"secondary_y": False}], [{"secondary_y": True}]],
            subplot_titles=("Dew Point Margin (°C) — Condensation Risk",
                            "PID Response — Valve Bypass vs Secondary Flow"))
        fig3.add_trace(go.Scatter(x=ds["Timestamp"], y=ds["Dew Point Margin (°C)"],
            name="Dew Point Margin", line=dict(color="#e3b341", width=2)), row=1, col=1)
        # Shade danger zone below 2 °C
        fig3.add_hrect(y0=-50, y1=2, fillcolor="#f85149", opacity=0.08,
                       line_width=0, row=1, col=1)
        fig3.add_hline(y=2, line=dict(color="#f85149", width=1, dash="dash"),
                       annotation_text="2 °C safety margin", annotation_font_color="#f85149",
                       annotation_position="top right", row=1, col=1)
        fig3.add_hline(y=0, line=dict(color="#f85149", width=1.5, dash="solid"),
                       annotation_text="0 °C — condensation starts",
                       annotation_font_color="#f85149", annotation_position="bottom right",
                       row=1, col=1)
        # PID response
        if "Valve Bypass Reading" in ds.columns:
            fig3.add_trace(go.Scatter(x=ds["Timestamp"], y=ds["Valve Bypass Reading"],
                fill="tozeroy", name="Valve Bypass (%)", opacity=0.4,
                line=dict(color="#ffa657", width=1.5)),
                row=2, col=1, secondary_y=False)
        if "Secondary Flowrate Reading" in ds.columns:
            fig3.add_trace(go.Scatter(x=ds["Timestamp"], y=ds["Secondary Flowrate Reading"],
                name="Secondary Flow (LPM)", line=dict(color="#3fb950", width=2)),
                row=2, col=1, secondary_y=True)
        fig3.update_yaxes(title_text="Margin (°C)", row=1, col=1)
        fig3.update_yaxes(title_text="Bypass (%)", row=2, col=1, secondary_y=False)
        fig3.update_yaxes(title_text="Flow (LPM)", row=2, col=1, secondary_y=True, showgrid=False)
        fig3.update_xaxes(showticklabels=True, tickformat="%b %d\n%H:%M")
        fig3.update_layout(**CHART, height=600)
        fig3.update_layout(margin=_MULTI_MARGIN, legend=_MULTI_LEGEND)
        style_fig(fig3)
        st.plotly_chart(fig3, use_container_width=True, config=PLOTLY_CONFIG)
        st.caption("Dew Point Margin = Secondary Supply Temp − Dew Point. Below 2 °C = condensation risk on server components. "
                   "PID row: the valve bypass should open when secondary flow demand rises — lag or hunting indicates PID tuning issues.")

# ════════════════════════════════════════════════════════
# 📊 CUSTOM EXPLORER
# ════════════════════════════════════════════════════════
with tabs[9]:
    if sys_df_f.empty:
        st.warning("No system_log data found.")
    else:
        # Build a categorised list of plottable columns
        _SKIP_PATTERNS = re.compile(
            r'abnormal|enabled|disabled|switch|status|reset|ready|_src',
            re.I)
        _plot_cols = sorted(
            [c for c in sys_df_f.columns
             if c != "Timestamp"
             and pd.api.types.is_numeric_dtype(sys_df_f[c])
             and not _SKIP_PATTERNS.search(c)],
            key=lambda c: (
                0 if "Temperature" in c else
                1 if "Pressure" in c else
                2 if "Flow" in c else
                3 if "Speed" in c else
                4 if "Power" in c or "Heat" in c or "Voltage" in c else
                5 if "Valve" in c or "Duty" in c else
                6 if "Setpoint" in c else
                7
            )
        )

        st.markdown('<p class="section-header">Build your own chart — select any fields to overlay</p>',
                    unsafe_allow_html=True)

        col_l, col_r = st.columns([1, 1])
        with col_l:
            left_fields = st.multiselect(
                "Left Y-axis fields",
                options=_plot_cols,
                default=[c for c in ["Secondary Return Temperature Reading",
                                     "Secondary Supply Temperature Reading"] if c in _plot_cols],
                help="All selected fields share the left Y-axis (same unit recommended).",
            )
        with col_r:
            right_fields = st.multiselect(
                "Right Y-axis fields (optional — use for different units)",
                options=_plot_cols,
                default=[],
                help="Plotted on the right Y-axis. Useful for overlaying e.g. flow on a temperature chart.",
            )

        # Reference line
        ref_col1, ref_col2 = st.columns([1, 3])
        with ref_col1:
            add_ref = st.checkbox("Add horizontal reference line", value=False)
        with ref_col2:
            ref_val = st.number_input("Reference line Y value", value=0.0, step=1.0,
                                      disabled=not add_ref, label_visibility="collapsed")

        if not left_fields and not right_fields:
            st.info("Select at least one field above to plot.")
        else:
            ds = downsample(sys_df_f, resolution)
            has_right = bool(right_fields)
            fig_c = make_subplots(specs=[[{"secondary_y": has_right}]])

            for i, col in enumerate(left_fields):
                if col in ds.columns:
                    fig_c.add_trace(
                        go.Scatter(x=ds["Timestamp"], y=ds[col], name=col,
                                   line=dict(color=PAL[i % len(PAL)], width=2)),
                        secondary_y=False)

            for i, col in enumerate(right_fields):
                if col in ds.columns:
                    fig_c.add_trace(
                        go.Scatter(x=ds["Timestamp"], y=ds[col], name=f"{col} (R)",
                                   line=dict(color=PAL[(i + len(left_fields)) % len(PAL)],
                                             width=2, dash="dot")),
                        secondary_y=True)

            if add_ref:
                fig_c.add_hline(y=ref_val, line=dict(color="#f85149", width=1.5, dash="dash"),
                                annotation_text=str(ref_val), annotation_font_color="#f85149",
                                annotation_position="top right")

            # Y-axis labels
            def _unit(col):
                if "Temperature" in col: return "°C"
                if "Pressure"    in col: return "kPa"
                if "Flow"        in col: return "LPM"
                if "Speed"       in col: return "RPM"
                if "Power" in col or "Heat" in col: return "W"
                if "Voltage"     in col: return "V"
                if "Duty" in col or "Valve" in col or "Humidity" in col: return "%"
                return ""
            left_unit  = ", ".join(u for u in dict.fromkeys(_unit(c) for c in left_fields)  if u) or "Value"
            right_unit = ", ".join(u for u in dict.fromkeys(_unit(c) for c in right_fields) if u) or "Value"

            fig_c.update_yaxes(title_text=left_unit, secondary_y=False)
            if has_right:
                fig_c.update_yaxes(title_text=right_unit, secondary_y=True, showgrid=False)
            fig_c.update_xaxes(tickformat="%b %d\n%H:%M")
            fig_c.update_layout(**CHART, height=520)
            style_fig(fig_c)
            add_rangeselector(fig_c)
            st.plotly_chart(fig_c, use_container_width=True, config=PLOTLY_CONFIG)
