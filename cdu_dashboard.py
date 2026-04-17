"""
Gen3 CDU CW — Full Log Dashboard
==================================
Parsers tuned to exact log formats:

  alert_log_1.log:
    [YYYY-MM-DD HH:MM:SS] <Alarm Name> asserted|deasserted

  api_access.log(.1-.5):
    YYYY-MM-DD HH:MM:SS - INFO|ERROR - METHOD /endpoint - STATUS - XXX.XXms - client_ip

  system_log_*.csv:
    Timestamp, <101 sensor/alarm columns>

  verbose_logs/cdu_app.log, web_app.log, modbus_*.log, etc.
  config/*.json
  system_health.txt

Requirements:  pip install dash plotly pandas
Run:           python cdu_dashboard.py
Open:          http://127.0.0.1:8050
"""

import dash
from dash import dcc, html, Input, Output, State, callback_context
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
import os, glob, re, json, base64, io
from pathlib import Path
from collections import defaultdict, Counter

# ─────────────────────────────────────────────────────────────────────────────
# THEME
# ─────────────────────────────────────────────────────────────────────────────
BG, CARD, BORDER = "#0d1117", "#161b22", "#30363d"
ACCENT, GREEN, YELLOW, RED, ORANGE, PURPLE = "#58a6ff","#3fb950","#d29922","#f85149","#e3b341","#bc8cff"
TEXT, SUBTEXT = "#c9d1d9", "#6e7681"
PAL = [ACCENT, PURPLE, "#79c0ff", GREEN, ORANGE, RED, "#ffa657", "#56d364"]

S_CARD = {"backgroundColor": CARD, "border": f"1px solid {BORDER}",
           "borderRadius": "10px", "padding": "16px", "marginBottom": "14px"}
S_LBL  = {"color": SUBTEXT, "fontSize": "11px", "fontWeight": "600",
           "textTransform": "uppercase", "letterSpacing": "1px", "marginBottom": "3px"}
S_INP  = {"width": "100%", "backgroundColor": BG, "color": TEXT,
           "border": f"1px solid {BORDER}", "borderRadius": "6px",
           "padding": "7px 10px", "fontSize": "13px", "boxSizing": "border-box",
           "marginBottom": "8px"}
CHART = dict(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color=TEXT, size=11), margin=dict(l=55, r=20, t=44, b=40),
    legend=dict(bgcolor="rgba(0,0,0,0)", bordercolor=BORDER, borderwidth=1,
                orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    xaxis=dict(gridcolor=BORDER, zerolinecolor=BORDER),
    yaxis=dict(gridcolor=BORDER, zerolinecolor=BORDER),
    hovermode="x unified",
)

def sec(t):
    return html.H3(t, style={"color": TEXT, "fontSize": "13px", "fontWeight": "600",
        "borderBottom": f"1px solid {BORDER}", "paddingBottom": "7px",
        "marginBottom": "12px", "marginTop": "0"})

def badge(txt, color=ACCENT):
    return html.Span(txt, style={"backgroundColor": color+"22", "color": color,
        "border": f"1px solid {color}44", "borderRadius": "12px",
        "padding": "2px 9px", "fontSize": "11px", "fontWeight": "600", "marginRight": "5px"})

def kpi(title, value, unit="", color=TEXT):
    return html.Div([
        html.Div(title, style=S_LBL),
        html.Div([
            html.Span(value, style={"color": color, "fontSize": "21px", "fontWeight": "700"}),
            html.Span(f" {unit}", style={"color": SUBTEXT, "fontSize": "12px"}) if unit else None,
        ]),
    ], style={**S_CARD, "minWidth": "140px", "flex": "1", "marginBottom": "0"})

def th(t): return html.Th(t, style={"padding": "7px 12px",
    "borderBottom": f"1px solid {BORDER}", "color": SUBTEXT, "fontSize": "11px", "textAlign": "left"})

def td(t, color=TEXT): return html.Td(str(t)[:180], style={"padding": "5px 12px",
    "fontSize": "11px", "borderBottom": f"1px solid {BORDER}22", "color": color})

def tbl(headers, rows_data, max_h="400px"):
    return html.Div(html.Table([
        html.Thead(html.Tr([th(h) for h in headers])),
        html.Tbody(rows_data),
    ], style={"width": "100%", "borderCollapse": "collapse"}),
    style={"overflowX": "auto", "maxHeight": max_h, "overflowY": "auto"})

def short(col):
    for s in [" Reading", " Abnormal", " Setpoint", " Enabled/Disabled"]:
        col = col.replace(s, "")
    return col

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

# ─────────────────────────────────────────────────────────────────────────────
# PARSERS
# ─────────────────────────────────────────────────────────────────────────────

def read_text(path):
    for enc in ("utf-8","utf-8-sig","latin-1","cp1252"):
        try:
            with open(path, "r", encoding=enc, errors="replace") as f:
                return f.read()
        except: pass
    return ""

def read_tail(path, max_bytes=500_000):
    """Read last max_bytes of a potentially huge log file."""
    size = os.path.getsize(path)
    for enc in ("utf-8","utf-8-sig","latin-1","cp1252"):
        try:
            with open(path, "r", encoding=enc, errors="replace") as f:
                if size > max_bytes:
                    f.seek(size - max_bytes)
                    f.readline()   # skip partial line
                lines = f.readlines()
            return lines
        except: pass
    return []

# ── system_log_*.csv ─────────────────────────────────────────────────────────
def load_system_logs(unit_path):
    cdu = os.path.join(unit_path, "cdu")
    files = sorted(glob.glob(os.path.join(cdu, "system_log*.csv")))
    if not files:
        return pd.DataFrame()
    frames = []
    for fp in files:
        try:
            df = pd.read_csv(fp, low_memory=False)
            df["_src"] = os.path.basename(fp)
            frames.append(df)
        except Exception as e:
            print(f"  ⚠ {fp}: {e}")
    if not frames: return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)
    out["Timestamp"] = pd.to_datetime(out["Timestamp"], errors="coerce")
    return out.dropna(subset=["Timestamp"]).sort_values("Timestamp").reset_index(drop=True)

# ── alert_log_1.log ──────────────────────────────────────────────────────────
# Format: [YYYY-MM-DD HH:MM:SS] <Alarm Name> asserted|deasserted
def parse_alert_log(unit_path):
    path = os.path.join(unit_path, "cdu", "alert_log_1.log")
    if not os.path.exists(path): return pd.DataFrame()
    text = read_text(path)
    pat = re.compile(
        r'\[(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\]\s+(.+?)\s+(asserted|deasserted)',
        re.IGNORECASE
    )
    rows = []
    for m in pat.finditer(text):
        rows.append({
            "Timestamp": pd.to_datetime(m.group(1)),
            "Alarm":     m.group(2).strip(),
            "State":     m.group(3).lower(),
        })
    if not rows: return pd.DataFrame()
    return pd.DataFrame(rows).sort_values("Timestamp").reset_index(drop=True)

# ── api_access.log(.1-.5) ─────────────────────────────────────────────────────
# Format: YYYY-MM-DD HH:MM:SS - INFO|ERROR - METHOD /path - STATUS - XXX.XXms - ip
def parse_api_access(unit_path):
    cdu   = os.path.join(unit_path, "cdu")
    files = sorted(glob.glob(os.path.join(cdu, "api_access.log*")))
    if not files: return pd.DataFrame()

    # Pattern for normal request lines
    req_pat = re.compile(
        r'(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})\s+-\s+'
        r'(INFO|ERROR|WARN\w*)\s+-\s+'
        r'(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\s+'
        r'(/[^\s]+)\s+-\s+'
        r'(\d+)\s+-\s+'
        r'([\d.]+)ms\s+-\s+'
        r'([\S]+)'
    )
    rows = []
    for fp in sorted(files, reverse=True):   # newest first so we get latest data
        lines = read_tail(fp, max_bytes=300_000)
        for line in lines:
            m = req_pat.search(line)
            if m:
                rows.append({
                    "Timestamp":     pd.to_datetime(m.group(1)),
                    "Level":         m.group(2),
                    "Method":        m.group(3),
                    "Endpoint":      m.group(4),
                    "Status":        int(m.group(5)),
                    "ResponseMs":    float(m.group(6)),
                    "Client":        m.group(7).replace("::ffff:",""),
                    "_file":         os.path.basename(fp),
                })
    if not rows: return pd.DataFrame()
    df = pd.DataFrame(rows).drop_duplicates()
    return df.sort_values("Timestamp").reset_index(drop=True)

# ── event_log_1.log ──────────────────────────────────────────────────────────
def parse_event_log(unit_path):
    path = os.path.join(unit_path, "cdu", "event_log_1.log")
    if not os.path.exists(path): return pd.DataFrame()
    text = read_text(path)
    ts_pat = re.compile(r'(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2})')
    rows = []
    for line in text.splitlines():
        if not line.strip(): continue
        m = ts_pat.search(line)
        rows.append({
            "Timestamp": pd.to_datetime(m.group(1)) if m else pd.NaT,
            "Message": line.strip(),
        })
    df = pd.DataFrame(rows).dropna(subset=["Timestamp"])
    return df.sort_values("Timestamp").reset_index(drop=True)

# ── verbose_logs/ ─────────────────────────────────────────────────────────────
VERBOSE_TARGETS = [
    "cdu_app.log","web_app.log","modbus_tcp_server.log",
    "modbus_rtu_server.log","metadata_app.log","update_log_manager.log",
    "log_manager.log","di_manager.log","certificate.log",
]
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
            rows.append({
                "Timestamp": pd.to_datetime(ts_m.group(1), errors="coerce"),
                "Level": lvl_m.group(1).upper() if lvl_m else "INFO",
                "Log": log_name,
                "Message": line[:300],
            })
    if not rows: return pd.DataFrame()
    df = pd.DataFrame(rows).dropna(subset=["Timestamp"])
    return df.sort_values("Timestamp").reset_index(drop=True)

# ── EventLog_*.txt ────────────────────────────────────────────────────────────
def parse_event_txts(unit_path):
    vdir = os.path.join(unit_path, "verbose_logs")
    if not os.path.isdir(vdir): return []
    return [{"file": os.path.basename(fp), "content": read_text(fp).strip()}
            for fp in sorted(glob.glob(os.path.join(vdir, "EventLog_*.txt")))]

# ── system_health.txt ─────────────────────────────────────────────────────────
def parse_health(unit_path):
    path = os.path.join(unit_path, "system_health.txt")
    if not os.path.exists(path): return {}
    data = {}
    for line in read_text(path).splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            data[k.strip()] = v.strip()
    return data

# ── config/*.json ─────────────────────────────────────────────────────────────
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

# ── helpers ───────────────────────────────────────────────────────────────────
def find_units(root):
    units = []
    for item in sorted(os.listdir(root)):
        full = os.path.join(root, item)
        if os.path.isdir(full) and os.path.isdir(os.path.join(full, "cdu")):
            units.append({"label": item, "value": full})
    return units

def downsample(df, n=2000):
    if df is None or df.empty or len(df) <= n: return df
    return df.iloc[::max(1, len(df)//n)]

def _deserialize(store):
    """Deserialize JSON store to DataFrame — result cached by caller."""
    if not store:
        return None
    df = pd.read_json(io.StringIO(store), orient="split")
    if "Timestamp" in df.columns:
        df["Timestamp"] = pd.to_datetime(df["Timestamp"])
    return df if not df.empty else None

def get_df(store, start=None, end=None):
    df = _deserialize(store)
    if df is None:
        return None
    if "Timestamp" in df.columns:
        if start: df = df[df["Timestamp"] >= pd.Timestamp(start)]
        if end:   df = df[df["Timestamp"] <= pd.Timestamp(end) + pd.Timedelta(days=1)]
    return df if not df.empty else None

def active_alarms(df):
    return [(c, int(df[c].sum())) for c in ALARM_COLS
            if c in df.columns and df[c].sum() > 0]

def sev(v):
    if v > 1000: return "Critical", RED
    if v > 100:  return "Warning",  YELLOW
    return "Minor", ACCENT

# ─────────────────────────────────────────────────────────────────────────────
# APP LAYOUT
# ─────────────────────────────────────────────────────────────────────────────
app = dash.Dash(__name__, title="CDU Log Dashboard",
                meta_tags=[{"name": "viewport", "content": "width=device-width"}])

from flask_caching import Cache
cache = Cache(app.server, config={"CACHE_TYPE": "SimpleCache", "CACHE_DEFAULT_TIMEOUT": 300})

app.layout = html.Div([

    # TOP BAR
    html.Div([
        html.Div([
            html.Span("⚙", style={"fontSize": "22px", "marginRight": "10px"}),
            html.Div([
                html.Div("Gen3 CDU CW — Log Dashboard",
                         style={"color": TEXT, "fontWeight": "700", "fontSize": "17px"}),
                html.Div([
                    badge("system_log", ACCENT), badge("alert_log", RED),
                    badge("event_log", YELLOW), badge("api_access", GREEN),
                    badge("verbose_logs", PURPLE),
                ], style={"marginTop": "4px"}),
            ]),
        ], style={"display": "flex", "alignItems": "center"}),
        html.Div(id="unit-badge",
                 style={"color": SUBTEXT, "fontSize": "12px", "textAlign": "right"}),
    ], style={"backgroundColor": CARD, "borderBottom": f"1px solid {BORDER}",
              "padding": "13px 24px", "display": "flex",
              "justifyContent": "space-between", "alignItems": "center"}),

    # BODY
    html.Div([

        # ── SIDEBAR ───────────────────────────────────────────────────────────
        html.Div([

            html.Div([
                sec("📂 Load Unit Folder"),
                html.Div("Paste the path to a CDU unit folder (contains cdu/, config/, verbose_logs/)",
                         style={"color": SUBTEXT, "fontSize": "11px", "marginBottom": "8px"}),
                dcc.Input(id="folder-path", style=S_INP, debounce=True,
                          placeholder=r"e.g. C:\...\02242026 Logs\0511202500MS DH4 263"),
                html.Div(id="unit-dropdown-div"),
                html.Button("🔄  Load", id="load-btn",
                    style={"backgroundColor": ACCENT, "color": BG, "border": "none",
                           "borderRadius": "6px", "padding": "9px 14px",
                           "cursor": "pointer", "fontWeight": "700",
                           "width": "100%", "fontSize": "13px", "marginBottom": "8px"}),
                html.Div(id="load-status",
                         style={"color": SUBTEXT, "fontSize": "11px", "minHeight": "16px"}),
            ], style=S_CARD),

            html.Div([
                sec("🔍 Filter"),
                html.Div("Date Range", style=S_LBL),
                dcc.DatePickerRange(id="date-range", display_format="MMM DD YYYY",
                    style={"marginBottom": "12px", "width": "100%"}),
                html.Div("Chart Resolution", style=S_LBL),
                dcc.Slider(id="resolution", min=500, max=5000, step=500, value=2000,
                    marks={500: "Fast", 2000: "Balanced", 5000: "Full"},
                    tooltip={"placement": "bottom"}),
            ], style=S_CARD),

            html.Div([
                sec("📁 Loaded Files"),
                html.Div(id="file-inventory",
                         style={"color": SUBTEXT, "fontSize": "11px", "lineHeight": "2"}),
            ], style=S_CARD),

        ], style={"width": "270px", "flexShrink": "0", "marginRight": "16px"}),

        # ── MAIN ──────────────────────────────────────────────────────────────
        html.Div([
            html.Div(id="kpi-row",
                     style={"display": "flex", "gap": "10px", "flexWrap": "wrap",
                            "marginBottom": "14px"}),

            dcc.Tabs(id="tabs", value="sensor", children=[
                dcc.Tab(label="📈  Sensors",         value="sensor"),
                dcc.Tab(label="🚨  Alarms",           value="alarms"),
                dcc.Tab(label="🌡  Temp & Flow",      value="temp"),
                dcc.Tab(label="⚙️  Pumps & Power",    value="pumps"),
                dcc.Tab(label="🌐  API Traffic",      value="api"),
                dcc.Tab(label="📋  App Logs",         value="applogs"),
                dcc.Tab(label="📣  Alert / Events",   value="events"),
                dcc.Tab(label="🔧  Config & Health",  value="config"),
            ], colors={"border": BORDER, "primary": ACCENT, "background": CARD},
               style={"marginBottom": "14px"}),

            html.Div(id="tab-content"),
        ], style={"flex": "1", "minWidth": "0"}),

    ], style={"display": "flex", "padding": "18px",
              "minHeight": "calc(100vh - 68px)"}),

    # Stores
    dcc.Store(id="s-sys"),
    dcc.Store(id="s-alert"),
    dcc.Store(id="s-event"),
    dcc.Store(id="s-api"),
    dcc.Store(id="s-verbose"),
    dcc.Store(id="s-config"),
    dcc.Store(id="s-health"),
    dcc.Store(id="s-evttxt"),

], style={"backgroundColor": BG, "fontFamily": "'Segoe UI', Inter, sans-serif",
          "minHeight": "100vh", "color": TEXT})


# ─────────────────────────────────────────────────────────────────────────────
# CALLBACKS
# ─────────────────────────────────────────────────────────────────────────────

@app.callback(
    Output("unit-dropdown-div", "children"),
    Input("folder-path", "value"),
)
def show_units(path):
    # Always render unit-select (even if hidden) so the Load callback can reference it
    hidden_select = dcc.Dropdown(id="unit-select", options=[], value=None,
                                 style={"display": "none"})
    if not path or not os.path.isdir(path.strip()):
        return html.Div(hidden_select)
    units = find_units(path.strip())
    if not units:
        return html.Div([
            html.Div("✓ This is the unit folder — click Load.",
                     style={"color": GREEN, "fontSize": "11px", "marginBottom": "8px"}),
            hidden_select,
        ])
    return html.Div([
        html.Div("Unit folders detected:", style={**S_LBL, "marginBottom": "5px"}),
        dcc.Dropdown(id="unit-select", options=units, value=units[0]["value"],
            style={"backgroundColor": BG, "fontSize": "12px", "marginBottom": "8px"}),
    ])


@app.callback(
    Output("s-sys",     "data"),
    Output("s-alert",   "data"),
    Output("s-event",   "data"),
    Output("s-api",     "data"),
    Output("s-verbose", "data"),
    Output("s-config",  "data"),
    Output("s-health",  "data"),
    Output("s-evttxt",  "data"),
    Output("load-status", "children"),
    Output("date-range", "min_date_allowed"),
    Output("date-range", "max_date_allowed"),
    Output("date-range", "start_date"),
    Output("date-range", "end_date"),
    Output("file-inventory", "children"),
    Output("unit-badge", "children"),
    Input("load-btn", "n_clicks"),
    State("folder-path", "value"),
    State("unit-select", "value") if True else State("folder-path", "value"),
    prevent_initial_call=True,
)
def load_unit(_, folder, unit_val):
    if not folder:
        return [None]*8 + ["⚠ Enter a path.", None, None, None, None, "", ""]
    folder = folder.strip()
    unit   = unit_val if (unit_val and os.path.isdir(str(unit_val))) else folder
    if not os.path.isdir(unit):
        return [None]*8 + [f"❌ Not found: {unit}", None, None, None, None, "", ""]

    name = os.path.basename(unit)
    print(f"\n  ▶ Loading: {name}")

    sys_df  = load_system_logs(unit)
    alrt_df = parse_alert_log(unit)
    evnt_df = parse_event_log(unit)
    api_df  = parse_api_access(unit)
    verb_df = parse_verbose_logs(unit)
    configs = load_configs(unit)
    health  = parse_health(unit)
    evttxts = parse_event_txts(unit)

    def j(df): return df.to_json(date_format="iso", orient="split") if df is not None and not df.empty else None

    mn = mx = None
    if not sys_df.empty:
        mn, mx = sys_df["Timestamp"].min().date(), sys_df["Timestamp"].max().date()

    # File inventory panel
    def row(icon, label, n, color=ACCENT):
        return html.Div([
            html.Span(icon, style={"marginRight": "5px"}),
            html.Span(label + "  ", style={"color": color, "fontWeight": "600"}),
            html.Span(f"{n:,}", style={"color": SUBTEXT}),
        ])

    inv = [
        row("📊", "Sensor rows",   len(sys_df),  ACCENT),
        row("🚨", "Alert events",  len(alrt_df), RED),
        row("📣", "Event entries", len(evnt_df), YELLOW),
        row("🌐", "API requests",  len(api_df),  GREEN),
        row("📋", "Verbose rows",  len(verb_df), PURPLE),
        row("⚙",  "Config files",  len(configs)),
        row("📄", "EventLog txts", len(evttxts)),
    ]

    return (
        j(sys_df), j(alrt_df), j(evnt_df), j(api_df), j(verb_df),
        json.dumps(configs), json.dumps(health), json.dumps(evttxts),
        f"✅  {name}",
        mn, mx, str(mn) if mn else None, str(mx) if mx else None,
        inv, f"Unit: {name}",
    )


# ── KPI row ───────────────────────────────────────────────────────────────────
@app.callback(
    Output("kpi-row", "children"),
    Input("s-sys",     "data"), Input("s-alert", "data"),
    Input("s-api",     "data"), Input("s-verbose","data"),
    Input("date-range","start_date"), Input("date-range","end_date"),
)
def update_kpis(sys_j, alrt_j, api_j, verb_j, start, end):
    sys_df  = get_df(sys_j,  start, end)
    alrt_df = get_df(alrt_j, start, end)
    api_df  = get_df(api_j,  start, end)
    verb_df = get_df(verb_j, start, end)
    if sys_df is None:
        return [html.Div("Load a unit folder to see KPIs.",
                         style={"color": SUBTEXT, "padding": "20px"})]

    dur       = (sys_df["Timestamp"].max()-sys_df["Timestamp"].min()).total_seconds()/3600
    alarms    = active_alarms(sys_df)
    n_ev      = sum(v for _,v in alarms)
    avg_t     = sys_df["Primary Supply Temperature Reading"].mean() \
                if "Primary Supply Temperature Reading" in sys_df.columns else None
    avg_p     = sys_df["Total Power Consumption Reading"].mean() \
                if "Total Power Consumption Reading" in sys_df.columns else None
    api_err   = int((api_df["Status"]>=400).sum()) if api_df is not None and "Status" in api_df.columns else 0
    app_err   = int((verb_df["Level"]=="ERROR").sum()) if verb_df is not None and "Level" in verb_df.columns else 0
    alert_cnt = len(alrt_df) if alrt_df is not None else 0

    return [
        kpi("Duration",       f"{dur:.1f}", "hrs"),
        kpi("Sensor Records", f"{len(sys_df):,}"),
        kpi("Alarm Types",    str(len(alarms)),  color=RED if alarms else GREEN),
        kpi("Alarm Events",   f"{n_ev:,}",        color=RED if n_ev else GREEN),
        kpi("Alert Entries",  str(alert_cnt),     color=RED if alert_cnt else GREEN),
        kpi("API Errors",     str(api_err),       color=RED if api_err else GREEN),
        kpi("App Errors",     str(app_err),       color=RED if app_err else GREEN),
        kpi("Avg Supply Temp",f"{avg_t:.1f}" if avg_t else "—", "°C"),
        kpi("Avg Power",      f"{avg_p:.0f}" if avg_p else "—", "W"),
    ]


# ── Tab content ───────────────────────────────────────────────────────────────
@app.callback(
    Output("tab-content", "children"),
    Input("tabs","value"),
    Input("s-sys","data"), Input("s-alert","data"), Input("s-event","data"),
    Input("s-api","data"), Input("s-verbose","data"),
    Input("s-config","data"), Input("s-health","data"), Input("s-evttxt","data"),
    Input("date-range","start_date"), Input("date-range","end_date"),
    Input("resolution","value"),
)
def render_tab(tab, sys_j, alrt_j, evnt_j, api_j, verb_j,
               cfg_j, hlth_j, evttxt_j, start, end, res):

    if not any([sys_j, alrt_j, api_j, verb_j]):
        return html.Div("📂 Enter a unit folder path and click Load.",
                        style={"color": SUBTEXT, "padding": "60px",
                               "textAlign": "center", "fontSize": "15px"})

    # Only deserialize stores needed for the active tab
    _sys_tabs = {"sensor", "alarms", "temp", "pumps"}
    sys_df  = get_df(sys_j, start, end) if tab in _sys_tabs else None
    L       = dict(**CHART)

    # ═════════════════════════════════════════════════════════
    # 📈 SENSOR OVERVIEW
    # ═════════════════════════════════════════════════════════
    if tab == "sensor":
        if sys_df is None:
            return html.Div("No system_log data.", style={"color": SUBTEXT, "padding": "40px"})
        ds = downsample(sys_df, res)
        fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.06,
            subplot_titles=("Temperature (°C)","Flow Rate (LPM)","Pressure (kPa)","Power (W)"))
        for i,col in enumerate([c for c in TEMP_COLS[:4] if c in ds.columns]):
            fig.add_trace(go.Scatter(x=ds["Timestamp"],y=ds[col],
                name=short(col),line=dict(color=PAL[i],width=1.5)),row=1,col=1)
        for i,col in enumerate([c for c in FLOW_COLS if c in ds.columns]):
            fig.add_trace(go.Scatter(x=ds["Timestamp"],y=ds[col],
                name=short(col),line=dict(color=PAL[i+2],width=1.5)),row=2,col=1)
        for i,col in enumerate([c for c in PRES_COLS[:2] if c in ds.columns]):
            fig.add_trace(go.Scatter(x=ds["Timestamp"],y=ds[col],
                name=short(col),line=dict(color=PAL[i+4],width=1.5)),row=3,col=1)
        for i,col in enumerate([c for c in POWER_COLS[:2] if c in ds.columns]):
            fig.add_trace(go.Scatter(x=ds["Timestamp"],y=ds[col],
                name=short(col),line=dict(color=PAL[i+6],width=1.5),
                fill="tozeroy" if i==0 else None),row=4,col=1)
        fig.update_layout(**L,height=700,showlegend=True)
        fig.update_xaxes(gridcolor=BORDER); fig.update_yaxes(gridcolor=BORDER)
        return html.Div([html.Div(dcc.Graph(figure=fig,config={"displayModeBar":False}),style=S_CARD)])

    # ═════════════════════════════════════════════════════════
    # 🚨 ALARMS
    # ═════════════════════════════════════════════════════════
    elif tab == "alarms":
        if sys_df is None:
            return html.Div("No system_log data.",style={"color":SUBTEXT,"padding":"40px"})
        alarms = active_alarms(sys_df)
        if not alarms:
            return html.Div([html.Div([
                html.Div("✅",style={"fontSize":"40px","textAlign":"center"}),
                html.Div("No alarms detected.",style={"color":GREEN,"textAlign":"center","marginTop":"8px"}),
            ],style=S_CARD)])
        s_al  = sorted(alarms,key=lambda x:x[1],reverse=True)
        vals  = [v for _,v in s_al]
        names = [short(k) for k,_ in s_al]

        bar = go.Figure(go.Bar(x=vals,y=names,orientation="h",
            marker_color=[sev(v)[1] for v in vals],
            text=[f"{v:,}" for v in vals],textposition="outside"))
        bar.update_layout(**L,title="Alarm Event Counts",height=max(300,len(s_al)*40))

        ac  = [k for k,_ in s_al]
        dfa = sys_df[["Timestamp"]+ac].set_index("Timestamp").resample("1H").sum().reset_index()
        heat = go.Figure(go.Heatmap(
            z=dfa[ac].T.values,x=dfa["Timestamp"],y=[short(c) for c in ac],
            colorscale=[[0,CARD],[0.01,YELLOW+"88"],[1,RED]],showscale=False))
        heat.update_layout(**L,title="Alarm Hourly Heatmap",height=max(240,len(ac)*32))

        rows = [html.Tr([td(short(k)),td(f"{v:,}",sev(v)[1]),td(sev(v)[0],sev(v)[1])])
                for k,v in s_al]
        return html.Div([
            html.Div(tbl(["Alarm","Count","Severity"],rows),style=S_CARD),
            html.Div(dcc.Graph(figure=bar, config={"displayModeBar":False}),style=S_CARD),
            html.Div(dcc.Graph(figure=heat,config={"displayModeBar":False}),style=S_CARD),
        ])

    # ═════════════════════════════════════════════════════════
    # 🌡 TEMP & FLOW
    # ═════════════════════════════════════════════════════════
    elif tab == "temp":
        if sys_df is None:
            return html.Div("No system_log data.",style={"color":SUBTEXT,"padding":"40px"})
        ds = downsample(sys_df,res)
        fig = make_subplots(rows=3,cols=1,shared_xaxes=True,vertical_spacing=0.08,
            subplot_titles=("Temperature (°C)","ΔT Primary (°C)","Flow Rate (LPM)"))
        for i,col in enumerate([c for c in TEMP_COLS if c in ds.columns]):
            fig.add_trace(go.Scatter(x=ds["Timestamp"],y=ds[col],
                name=short(col),line=dict(color=PAL[i],width=1.5)),row=1,col=1)
        if all(c in ds.columns for c in ["Primary Supply Temperature Reading",
                                          "Primary Return Temperature Reading"]):
            dt = ds["Primary Supply Temperature Reading"]-ds["Primary Return Temperature Reading"]
            fig.add_trace(go.Scatter(x=ds["Timestamp"],y=dt,fill="tozeroy",
                name="Primary ΔT",line=dict(color=YELLOW,width=1.5)),row=2,col=1)
        for i,col in enumerate([c for c in FLOW_COLS if c in ds.columns]):
            fig.add_trace(go.Scatter(x=ds["Timestamp"],y=ds[col],
                name=short(col),line=dict(color=PAL[i+4],width=1.5)),row=3,col=1)
        fig.update_layout(**L,height=600)
        fig.update_xaxes(gridcolor=BORDER); fig.update_yaxes(gridcolor=BORDER)
        return html.Div([html.Div(dcc.Graph(figure=fig,config={"displayModeBar":False}),style=S_CARD)])

    # ═════════════════════════════════════════════════════════
    # ⚙️ PUMPS & POWER
    # ═════════════════════════════════════════════════════════
    elif tab == "pumps":
        if sys_df is None:
            return html.Div("No system_log data.",style={"color":SUBTEXT,"padding":"40px"})
        ds = downsample(sys_df,res)
        fig = make_subplots(rows=3,cols=1,shared_xaxes=True,vertical_spacing=0.08,
            subplot_titles=("Pump Speed (RPM)","Duty Cycle (%)","Power & Heat (W)"))
        for i,col in enumerate([c for c in PUMP_COLS[:3] if c in ds.columns]):
            fig.add_trace(go.Scatter(x=ds["Timestamp"],y=ds[col],
                name=short(col),line=dict(color=PAL[i],width=1.5)),row=1,col=1)
        for i,col in enumerate([c for c in ["Pump Duty Reading","Fan Duty Reading"] if c in ds.columns]):
            fig.add_trace(go.Scatter(x=ds["Timestamp"],y=ds[col],fill="tozeroy",
                name=short(col),line=dict(color=PAL[i+3],width=1.5)),row=2,col=1)
        for i,col in enumerate([c for c in POWER_COLS if c in ds.columns]):
            fig.add_trace(go.Scatter(x=ds["Timestamp"],y=ds[col],
                name=short(col),line=dict(color=PAL[i+5],width=1.5)),row=3,col=1)
        fig.update_layout(**L,height=580)
        fig.update_xaxes(gridcolor=BORDER); fig.update_yaxes(gridcolor=BORDER)
        panels = [html.Div(dcc.Graph(figure=fig,config={"displayModeBar":False}),style=S_CARD)]
        if "Valve Bypass Reading" in ds.columns:
            vf = go.Figure(go.Scatter(x=ds["Timestamp"],y=ds["Valve Bypass Reading"],
                fill="tozeroy",name="Valve Bypass %",line=dict(color=ACCENT,width=1.5)))
            vf.update_layout(**L,title="Valve Bypass (%)",height=240)
            panels.append(html.Div(dcc.Graph(figure=vf,config={"displayModeBar":False}),style=S_CARD))
        return html.Div(panels)

    # ═════════════════════════════════════════════════════════
    # 🌐 API TRAFFIC
    # ═════════════════════════════════════════════════════════
    elif tab == "api":
        api_df = get_df(api_j, start, end)
        if api_df is None or api_df.empty:
            return html.Div("No API access log data found.",style={"color":SUBTEXT,"padding":"40px"})

        # 1. Request volume (15 min bins)
        vol = api_df.set_index("Timestamp").resample("15min").size().reset_index(name="count")
        fig_vol = go.Figure(go.Scatter(x=vol["Timestamp"],y=vol["count"],
            fill="tozeroy",name="Requests/15min",line=dict(color=GREEN,width=1.5)))
        fig_vol.update_layout(**L,title="API Request Volume (per 15 min)",height=260)

        # 2. Response time over time
        ds_api = downsample(api_df, 1500)
        fig_rt = go.Figure()
        fig_rt.add_trace(go.Scatter(x=ds_api["Timestamp"],y=ds_api["ResponseMs"],
            mode="markers",name="Response Time",
            marker=dict(color=[RED if s>=400 else GREEN for s in ds_api["Status"]],size=3,opacity=0.6)))
        fig_rt.update_layout(**L,title="API Response Time (ms) — 🔴 = error",height=260)

        # 3. Status code bar
        st = api_df["Status"].value_counts().sort_index()
        def st_color(s): return GREEN if s<300 else YELLOW if s<400 else RED
        fig_st = go.Figure(go.Bar(x=[str(s) for s in st.index],y=st.values,
            marker_color=[st_color(s) for s in st.index],
            text=st.values,textposition="outside"))
        fig_st.update_layout(**L,title="HTTP Status Codes",height=280,showlegend=False)

        # 4. Top 15 endpoints
        ep = api_df["Endpoint"].value_counts().head(15)
        fig_ep = go.Figure(go.Bar(x=ep.values,y=[e[:55] for e in ep.index],
            orientation="h",marker_color=ACCENT,
            text=ep.values,textposition="outside"))
        fig_ep.update_layout(**L,title="Top 15 Endpoints",
                             height=max(300,len(ep)*32),showlegend=False)

        # 5. Client IP breakdown
        fig_cl = go.Figure(go.Pie(
            labels=api_df["Client"].value_counts().index.tolist(),
            values=api_df["Client"].value_counts().values.tolist(),
            marker_colors=PAL, hole=0.42))
        fig_cl.update_layout(**L,title="Requests by Client IP",height=300)

        # 6. 404 error table
        errors_df = api_df[api_df["Status"]>=400].sort_values("Timestamp",ascending=False).head(100)
        err_rows  = [html.Tr([
            td(str(r["Timestamp"])[:19]), td(r["Method"],YELLOW),
            td(r["Endpoint"],SUBTEXT), td(str(r["Status"]),RED),
            td(f"{r['ResponseMs']:.0f} ms"), td(r["Client"]),
        ]) for _,r in errors_df.iterrows()]

        return html.Div([
            html.Div([
                html.Div(dcc.Graph(figure=fig_vol,config={"displayModeBar":False}),
                         style={**S_CARD,"flex":"1","marginBottom":"0"}),
                html.Div(dcc.Graph(figure=fig_rt, config={"displayModeBar":False}),
                         style={**S_CARD,"flex":"1","marginBottom":"0"}),
            ],style={"display":"flex","gap":"12px","marginBottom":"14px"}),
            html.Div([
                html.Div(dcc.Graph(figure=fig_st,config={"displayModeBar":False}),
                         style={**S_CARD,"flex":"1","marginBottom":"0"}),
                html.Div(dcc.Graph(figure=fig_cl,config={"displayModeBar":False}),
                         style={**S_CARD,"flex":"1","marginBottom":"0"}),
            ],style={"display":"flex","gap":"12px","marginBottom":"14px"}),
            html.Div(dcc.Graph(figure=fig_ep,config={"displayModeBar":False}),style=S_CARD),
            html.Div([
                html.Div(f"{len(errors_df)} API error responses (4xx/5xx) — newest first",
                         style={"color":RED,"fontSize":"12px","marginBottom":"8px"}),
                tbl(["Timestamp","Method","Endpoint","Status","Time","Client"],
                    err_rows, "320px"),
            ],style=S_CARD) if err_rows else html.Div(),
        ])

    # ═════════════════════════════════════════════════════════
    # 📋 APP LOGS
    # ═════════════════════════════════════════════════════════
    elif tab == "applogs":
        verb_df = get_df(verb_j, start, end)
        if verb_df is None or verb_df.empty:
            return html.Div("No verbose log data.",style={"color":SUBTEXT,"padding":"40px"})

        # Stacked bar: log level per log file
        pivot   = verb_df.groupby(["Log","Level"]).size().unstack(fill_value=0)
        lvl_c   = [c for c in ["ERROR","WARNING","WARN","INFO","DEBUG"] if c in pivot.columns]
        clr_map = {"ERROR":RED,"WARNING":YELLOW,"WARN":YELLOW,"INFO":ACCENT,"DEBUG":SUBTEXT}
        fig_lv  = go.Figure()
        for lvl in lvl_c:
            fig_lv.add_trace(go.Bar(name=lvl,x=pivot.index.tolist(),y=pivot[lvl].tolist(),
                marker_color=clr_map.get(lvl,PURPLE)))
        fig_lv.update_layout(**L,title="Log Level by Service",barmode="stack",height=340)

        errors  = verb_df[verb_df["Level"].isin(["ERROR","CRITICAL","FATAL"])].copy()
        panels  = [html.Div(dcc.Graph(figure=fig_lv,config={"displayModeBar":False}),style=S_CARD)]

        if not errors.empty:
            ev = errors.set_index("Timestamp").resample("1H").size().reset_index(name="errors")
            fe = go.Figure(go.Bar(x=ev["Timestamp"],y=ev["errors"],
                name="Errors/hr",marker_color=RED))
            fe.update_layout(**L,title="Error Rate Over Time",height=250)
            panels.append(html.Div(dcc.Graph(figure=fe,config={"displayModeBar":False}),style=S_CARD))

            err_rows = [html.Tr([
                td(str(r["Timestamp"])[:19]),
                td(r.get("Log",""),PURPLE),
                td(r["Level"],RED),
                td(r["Message"][:140],SUBTEXT),
            ]) for _,r in errors.head(250).iterrows()]
            panels.append(html.Div([
                html.Div(f"{len(errors)} ERROR entries (newest first, max 250 shown)",
                         style={"color":RED,"fontSize":"12px","marginBottom":"8px"}),
                tbl(["Timestamp","Service","Level","Message"],err_rows),
            ],style=S_CARD))

        return html.Div(panels)

    # ═════════════════════════════════════════════════════════
    # 📣 ALERT / EVENTS
    # ═════════════════════════════════════════════════════════
    elif tab == "events":
        alrt_df = get_df(alrt_j, start, end)
        evnt_df = get_df(evnt_j, start, end)
        evttxts = json.loads(evttxt_j) if evttxt_j else []
        panels  = []

        if alrt_df is not None and not alrt_df.empty:
            # Timeline: asserted vs deasserted per alarm
            alarms_list = alrt_df["Alarm"].unique().tolist()
            fig_tl = go.Figure()
            for i, alarm in enumerate(alarms_list):
                sub = alrt_df[alrt_df["Alarm"] == alarm]
                asr = sub[sub["State"] == "asserted"]
                das = sub[sub["State"] == "deasserted"]
                fig_tl.add_trace(go.Scatter(
                    x=asr["Timestamp"], y=[alarm]*len(asr),
                    mode="markers", name="asserted",
                    marker=dict(symbol="triangle-up", color=RED, size=10),
                    showlegend=(i==0)))
                fig_tl.add_trace(go.Scatter(
                    x=das["Timestamp"], y=[alarm]*len(das),
                    mode="markers", name="deasserted",
                    marker=dict(symbol="triangle-down", color=GREEN, size=10),
                    showlegend=(i==0)))
            fig_tl.update_layout(**L, title="Alert Timeline — ▲ Asserted  ▼ Deasserted",
                                  height=max(280, len(alarms_list)*50),
                                  yaxis=dict(gridcolor=BORDER))

            # Count per alarm
            cnt = alrt_df[alrt_df["State"]=="asserted"]["Alarm"].value_counts()
            fig_cnt = go.Figure(go.Bar(
                x=cnt.values, y=cnt.index.tolist(), orientation="h",
                marker_color=RED, text=cnt.values, textposition="outside"))
            fig_cnt.update_layout(**L, title="Alert Occurrences (asserted count)",
                                   height=max(250, len(cnt)*38), showlegend=False)

            # Duration table: asserted → deasserted pairs
            dur_rows = []
            for alarm in alarms_list:
                sub = alrt_df[alrt_df["Alarm"]==alarm].sort_values("Timestamp")
                last_on = None
                for _,r in sub.iterrows():
                    if r["State"]=="asserted":
                        last_on = r["Timestamp"]
                    elif r["State"]=="deasserted" and last_on is not None:
                        secs = (r["Timestamp"]-last_on).total_seconds()
                        dur_str = f"{int(secs//60)}m {int(secs%60)}s" if secs < 3600 else f"{secs/3600:.1f}h"
                        dur_rows.append(html.Tr([
                            td(str(last_on)[:19]),
                            td(alarm, YELLOW),
                            td(str(r["Timestamp"])[:19]),
                            td(dur_str, ORANGE),
                        ]))
                        last_on = None

            # Full log table
            all_rows = [html.Tr([
                td(str(r["Timestamp"])[:19]),
                td(r["Alarm"], YELLOW),
                td(r["State"], RED if r["State"]=="asserted" else GREEN),
            ]) for _,r in alrt_df.iterrows()]

            panels += [
                html.Div(dcc.Graph(figure=fig_tl, config={"displayModeBar":False}), style=S_CARD),
                html.Div([
                    html.Div(dcc.Graph(figure=fig_cnt, config={"displayModeBar":False}),
                             style={**S_CARD,"flex":"1","marginBottom":"0"}),
                    html.Div([
                        html.Div("Assert → Deassert Durations",
                                 style={"color":ORANGE,"fontSize":"12px","fontWeight":"600","marginBottom":"8px"}),
                        tbl(["Asserted At","Alarm","Deasserted At","Duration"],dur_rows,"300px"),
                    ], style={**S_CARD,"flex":"1","marginBottom":"0"}),
                ], style={"display":"flex","gap":"12px","marginBottom":"14px"}),
                html.Div([
                    html.Div(f"Full alert log — {len(alrt_df)} entries",
                             style={"color":SUBTEXT,"fontSize":"11px","marginBottom":"8px"}),
                    tbl(["Timestamp","Alarm","State"],all_rows,"300px"),
                ], style=S_CARD),
            ]

        if evnt_df is not None and not evnt_df.empty:
            rows = [html.Tr([td(str(r["Timestamp"])[:19]),td(r["Message"],SUBTEXT)])
                    for _,r in evnt_df.iterrows()]
            panels.append(html.Div([
                html.Div(f"event_log_1 — {len(evnt_df)} entries",
                         style={"color":YELLOW,"fontSize":"12px","marginBottom":"8px"}),
                tbl(["Timestamp","Event"],rows,"260px"),
            ],style=S_CARD))

        if evttxts:
            panels.append(html.Div([
                sec("EventLog_*.txt snapshots"),
                *[html.Div([
                    html.Div(e["file"],style={"color":ORANGE,"fontWeight":"600",
                                              "fontSize":"12px","marginBottom":"4px"}),
                    html.Pre(e["content"][:800],style={"color":SUBTEXT,"fontSize":"11px",
                        "backgroundColor":BG,"padding":"10px","borderRadius":"6px",
                        "whiteSpace":"pre-wrap","marginBottom":"10px"}),
                ]) for e in evttxts],
            ],style=S_CARD))

        return html.Div(panels) if panels else html.Div(
            "No alert/event data found.",style={"color":SUBTEXT,"padding":"40px"})

    # ═════════════════════════════════════════════════════════
    # 🔧 CONFIG & HEALTH
    # ═════════════════════════════════════════════════════════
    elif tab == "config":
        configs = json.loads(cfg_j)  if cfg_j  else {}
        health  = json.loads(hlth_j) if hlth_j else {}
        panels  = []

        if health:
            rows = [html.Tr([td(k,ACCENT),td(v)]) for k,v in list(health.items())[:50]]
            panels.append(html.Div([sec("system_health.txt"),
                tbl(["Key","Value"],rows,"300px")],style=S_CARD))

        for fname,cfg in configs.items():
            content = json.dumps(cfg,indent=2)
            panels.append(html.Div([
                html.Div(fname,style={"color":GREEN,"fontWeight":"600",
                                      "fontSize":"12px","marginBottom":"6px"}),
                html.Pre(content[:3000],style={"color":SUBTEXT,"fontSize":"11px",
                    "backgroundColor":BG,"padding":"10px","borderRadius":"6px",
                    "whiteSpace":"pre-wrap","maxHeight":"320px","overflowY":"auto"}),
            ],style=S_CARD))

        return html.Div(panels) if panels else html.Div(
            "No config/health data.",style={"color":SUBTEXT,"padding":"40px"})

    return html.Div("Select a tab.")


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print()
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║   Gen3 CDU CW — Full Log Dashboard                          ║")
    print("║   Open browser at:  http://127.0.0.1:8050                   ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()
    app.run(debug=False, port=8050)
