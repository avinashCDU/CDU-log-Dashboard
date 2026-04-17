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

PAL = ["#58a6ff","#bc8cff","#79c0ff","#3fb950","#e3b341","#f85149","#ffa657","#56d364"]

def short(col):
    for s in [" Reading"," Abnormal"," Setpoint"," Enabled/Disabled"]:
        col = col.replace(s, "")
    return col

def downsample(df, n=2000):
    if df is None or df.empty or len(df) <= n: return df
    return df.iloc[::max(1, len(df)//n)]

def active_alarms(df):
    return [(c, int(df[c].sum())) for c in ALARM_COLS
            if c in df.columns and df[c].sum() > 0]

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
    return out.dropna(subset=["Timestamp"]).sort_values("Timestamp").reset_index(drop=True)

@st.cache_data(show_spinner=False)
def parse_alert_log(unit_path):
    path = os.path.join(unit_path, "cdu", "alert_log_1.log")
    if not os.path.exists(path): return pd.DataFrame()
    text = read_text(path)
    pat  = re.compile(r'\[(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\]\s+(.+?)\s+(asserted|deasserted)', re.I)
    rows = [{"Timestamp": pd.to_datetime(m.group(1)),
             "Alarm": m.group(2).strip(), "State": m.group(3).lower()}
            for m in pat.finditer(text)]
    if not rows: return pd.DataFrame()
    return pd.DataFrame(rows).sort_values("Timestamp").reset_index(drop=True)

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
                rows.append({"Timestamp": pd.to_datetime(m.group(1)), "Level": m.group(2),
                             "Method": m.group(3), "Endpoint": m.group(4),
                             "Status": int(m.group(5)), "ResponseMs": float(m.group(6)),
                             "Client": m.group(7).replace("::ffff:",""), "_file": os.path.basename(fp)})
    if not rows: return pd.DataFrame()
    return pd.DataFrame(rows).drop_duplicates().sort_values("Timestamp").reset_index(drop=True)

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
        rows.append({"Timestamp": pd.to_datetime(m.group(1)) if m else pd.NaT,
                     "Message": line.strip()})
    return pd.DataFrame(rows).dropna(subset=["Timestamp"]).sort_values("Timestamp").reset_index(drop=True)

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
            rows.append({"Timestamp": pd.to_datetime(ts_m.group(1), errors="coerce"),
                         "Level": lvl_m.group(1).upper() if lvl_m else "INFO",
                         "Log": log_name, "Message": line[:300]})
    if not rows: return pd.DataFrame()
    return pd.DataFrame(rows).dropna(subset=["Timestamp"]).sort_values("Timestamp").reset_index(drop=True)

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

def find_units(root):
    units = []
    for item in sorted(os.listdir(root)):
        full = os.path.join(root, item)
        if os.path.isdir(full) and os.path.isdir(os.path.join(full, "cdu")):
            units.append(full)
    return units

def filter_by_date(df, start, end):
    if df is None or df.empty: return df
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
    mode = st.radio("Input mode", ["⬆️ Upload ZIP", "📁 Local Path"], horizontal=True)

    unit_path = None

    # ── ZIP UPLOAD MODE ───────────────────────────────────────────────────────
    if mode == "⬆️ Upload ZIP":
        st.caption("Zip the unit folder (must contain cdu/, config/, verbose_logs/) and upload it.")
        uploaded = st.file_uploader("Drop ZIP here", type="zip", label_visibility="collapsed")

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
                    st.error("ZIP doesn't contain a valid unit folder (no cdu/ subfolder found).")

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

    resolution = st.slider("Chart resolution", 500, 5000, 2000, 500,
                           help="Higher = more detail but slower")

    st.divider()

# ─────────────────────────────────────────────────────────────────────────────
# MAIN CONTENT
# ─────────────────────────────────────────────────────────────────────────────
if not unit_path:
    st.info("📂 Upload a ZIP file or paste a local folder path in the sidebar to get started.")
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

# Apply date filter
sys_df_f  = filter_by_date(sys_df,  start_date, end_date)
alrt_df_f = filter_by_date(alrt_df, start_date, end_date)
evnt_df_f = filter_by_date(evnt_df, start_date, end_date)
api_df_f  = filter_by_date(api_df,  start_date, end_date)
verb_df_f = filter_by_date(verb_df, start_date, end_date)

# Show loaded file inventory in sidebar
with st.sidebar:
    st.subheader("📁 Loaded Files")
    st.markdown(f"🔵 **Sensor rows:** {len(sys_df):,}")
    st.markdown(f"🔴 **Alert events:** {len(alrt_df):,}")
    st.markdown(f"🟡 **Event entries:** {len(evnt_df):,}")
    st.markdown(f"🟢 **API requests:** {len(api_df):,}")
    st.markdown(f"🟣 **Verbose rows:** {len(verb_df):,}")
    st.markdown(f"⚙️ **Config files:** {len(configs)}")
    st.markdown(f"📄 **EventLog txts:** {len(evttxts)}")

# Unit header
st.header(f"⚙️  {os.path.basename(unit_path)}")

# ── KPI row ───────────────────────────────────────────────────────────────────
if not sys_df_f.empty:
    alarms    = active_alarms(sys_df_f)
    n_ev      = sum(v for _, v in alarms)
    dur       = (sys_df_f["Timestamp"].max() - sys_df_f["Timestamp"].min()).total_seconds() / 3600
    avg_t     = sys_df_f["Primary Supply Temperature Reading"].mean() \
                if "Primary Supply Temperature Reading" in sys_df_f.columns else None
    avg_p     = sys_df_f["Total Power Consumption Reading"].mean() \
                if "Total Power Consumption Reading" in sys_df_f.columns else None
    api_err   = int((api_df_f["Status"] >= 400).sum()) if not api_df_f.empty and "Status" in api_df_f.columns else 0
    app_err   = int((verb_df_f["Level"] == "ERROR").sum()) if not verb_df_f.empty and "Level" in verb_df_f.columns else 0

    k1,k2,k3,k4,k5,k6,k7,k8,k9 = st.columns(9)
    k1.metric("Duration",        f"{dur:.1f} hrs")
    k2.metric("Sensor Records",  f"{len(sys_df_f):,}")
    k3.metric("Alarm Types",     str(len(alarms)))
    k4.metric("Alarm Events",    f"{n_ev:,}")
    k5.metric("Alert Entries",   str(len(alrt_df_f)))
    k6.metric("API Errors",      str(api_err))
    k7.metric("App Errors",      str(app_err))
    k8.metric("Avg Supply Temp", f"{avg_t:.1f} °C" if avg_t else "—")
    k9.metric("Avg Power",       f"{avg_p:.0f} W"  if avg_p else "—")

st.divider()

# ── TABS ──────────────────────────────────────────────────────────────────────
tabs = st.tabs(["📈 Sensors","🚨 Alarms","🌡 Temp & Flow",
                "⚙️ Pumps & Power","🌐 API Traffic",
                "📋 App Logs","📣 Alert / Events","🔧 Config & Health"])

CHART = dict(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font=dict(size=11), margin=dict(l=55, r=20, t=44, b=40),
    legend=dict(bgcolor="rgba(0,0,0,0)", orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    hovermode="x unified",
)

# ════════════════════════════════════════════════════════
# 📈 SENSORS
# ════════════════════════════════════════════════════════
with tabs[0]:
    if sys_df_f.empty:
        st.warning("No system_log data found.")
    else:
        ds = downsample(sys_df_f, resolution)
        fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.06,
            subplot_titles=("Temperature (°C)","Flow Rate (LPM)","Pressure (kPa)","Power (W)"))
        for i, col in enumerate([c for c in TEMP_COLS[:4] if c in ds.columns]):
            fig.add_trace(go.Scatter(x=ds["Timestamp"], y=ds[col], name=short(col),
                line=dict(color=PAL[i], width=1.5)), row=1, col=1)
        for i, col in enumerate([c for c in FLOW_COLS if c in ds.columns]):
            fig.add_trace(go.Scatter(x=ds["Timestamp"], y=ds[col], name=short(col),
                line=dict(color=PAL[i+2], width=1.5)), row=2, col=1)
        for i, col in enumerate([c for c in PRES_COLS[:2] if c in ds.columns]):
            fig.add_trace(go.Scatter(x=ds["Timestamp"], y=ds[col], name=short(col),
                line=dict(color=PAL[i+4], width=1.5)), row=3, col=1)
        for i, col in enumerate([c for c in POWER_COLS[:2] if c in ds.columns]):
            fig.add_trace(go.Scatter(x=ds["Timestamp"], y=ds[col], name=short(col),
                line=dict(color=PAL[i+6], width=1.5),
                fill="tozeroy" if i == 0 else None), row=4, col=1)
        fig.update_layout(**CHART, height=700)
        st.plotly_chart(fig, width="stretch")

# ════════════════════════════════════════════════════════
# 🚨 ALARMS
# ════════════════════════════════════════════════════════
with tabs[1]:
    if sys_df_f.empty:
        st.warning("No system_log data found.")
    else:
        alarms = active_alarms(sys_df_f)
        if not alarms:
            st.success("✅ No alarms detected.")
        else:
            s_al  = sorted(alarms, key=lambda x: x[1], reverse=True)
            vals  = [v for _, v in s_al]
            names = [short(k) for k, _ in s_al]

            def sev_color(v):
                return "#f85149" if v > 1000 else "#d29922" if v > 100 else "#58a6ff"

            col1, col2 = st.columns(2)
            with col1:
                bar = go.Figure(go.Bar(x=vals, y=names, orientation="h",
                    marker_color=[sev_color(v) for v in vals],
                    text=[f"{v:,}" for v in vals], textposition="outside"))
                bar.update_layout(**CHART, title="Alarm Event Counts", height=max(300, len(s_al)*40))
                st.plotly_chart(bar, width="stretch")

            with col2:
                ac  = [k for k, _ in s_al]
                dfa = sys_df_f[["Timestamp"]+ac].set_index("Timestamp").resample("1h").sum().reset_index()
                heat = go.Figure(go.Heatmap(
                    z=dfa[ac].T.values, x=dfa["Timestamp"], y=[short(c) for c in ac],
                    colorscale=[[0,"#161b22"],[0.01,"#d29922"],[1,"#f85149"]],showscale=False))
                heat.update_layout(**CHART, title="Alarm Hourly Heatmap", height=max(240, len(ac)*32))
                st.plotly_chart(heat, width="stretch")

            tbl_data = [{"Alarm": short(k), "Count": v,
                         "Severity": "Critical" if v>1000 else "Warning" if v>100 else "Minor"}
                        for k, v in s_al]
            st.dataframe(pd.DataFrame(tbl_data), width="stretch", hide_index=True)

# ════════════════════════════════════════════════════════
# 🌡 TEMP & FLOW
# ════════════════════════════════════════════════════════
with tabs[2]:
    if sys_df_f.empty:
        st.warning("No system_log data found.")
    else:
        ds = downsample(sys_df_f, resolution)
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.08,
            subplot_titles=("Temperature (°C)","ΔT Primary (°C)","Flow Rate (LPM)"))
        for i, col in enumerate([c for c in TEMP_COLS if c in ds.columns]):
            fig.add_trace(go.Scatter(x=ds["Timestamp"], y=ds[col], name=short(col),
                line=dict(color=PAL[i], width=1.5)), row=1, col=1)
        if all(c in ds.columns for c in ["Primary Supply Temperature Reading",
                                          "Primary Return Temperature Reading"]):
            dt = ds["Primary Supply Temperature Reading"] - ds["Primary Return Temperature Reading"]
            fig.add_trace(go.Scatter(x=ds["Timestamp"], y=dt, fill="tozeroy",
                name="Primary ΔT", line=dict(color="#d29922", width=1.5)), row=2, col=1)
        for i, col in enumerate([c for c in FLOW_COLS if c in ds.columns]):
            fig.add_trace(go.Scatter(x=ds["Timestamp"], y=ds[col], name=short(col),
                line=dict(color=PAL[i+4], width=1.5)), row=3, col=1)
        fig.update_layout(**CHART, height=600)
        st.plotly_chart(fig, width="stretch")

# ════════════════════════════════════════════════════════
# ⚙️ PUMPS & POWER
# ════════════════════════════════════════════════════════
with tabs[3]:
    if sys_df_f.empty:
        st.warning("No system_log data found.")
    else:
        ds = downsample(sys_df_f, resolution)
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.08,
            subplot_titles=("Pump Speed (RPM)","Duty Cycle (%)","Power & Heat (W)"))
        for i, col in enumerate([c for c in PUMP_COLS[:3] if c in ds.columns]):
            fig.add_trace(go.Scatter(x=ds["Timestamp"], y=ds[col], name=short(col),
                line=dict(color=PAL[i], width=1.5)), row=1, col=1)
        for i, col in enumerate([c for c in ["Pump Duty Reading","Fan Duty Reading"] if c in ds.columns]):
            fig.add_trace(go.Scatter(x=ds["Timestamp"], y=ds[col], fill="tozeroy",
                name=short(col), line=dict(color=PAL[i+3], width=1.5)), row=2, col=1)
        for i, col in enumerate([c for c in POWER_COLS if c in ds.columns]):
            fig.add_trace(go.Scatter(x=ds["Timestamp"], y=ds[col], name=short(col),
                line=dict(color=PAL[i+5], width=1.5)), row=3, col=1)
        fig.update_layout(**CHART, height=580)
        st.plotly_chart(fig, width="stretch")

        if "Valve Bypass Reading" in ds.columns:
            vf = go.Figure(go.Scatter(x=ds["Timestamp"], y=ds["Valve Bypass Reading"],
                fill="tozeroy", name="Valve Bypass %", line=dict(color="#58a6ff", width=1.5)))
            vf.update_layout(**CHART, title="Valve Bypass (%)", height=240)
            st.plotly_chart(vf, width="stretch")

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
        fig_vol.update_layout(**CHART, title="API Request Volume (per 15 min)", height=260)

        ds_api = downsample(api_df_f, 1500)
        fig_rt = go.Figure()
        fig_rt.add_trace(go.Scatter(x=ds_api["Timestamp"], y=ds_api["ResponseMs"], mode="markers",
            name="Response Time",
            marker=dict(color=["#f85149" if s >= 400 else "#3fb950" for s in ds_api["Status"]],
                        size=3, opacity=0.6)))
        fig_rt.update_layout(**CHART, title="API Response Time (ms) — 🔴 = error", height=260)

        col1, col2 = st.columns(2)
        with col1: st.plotly_chart(fig_vol, width="stretch")
        with col2: st.plotly_chart(fig_rt,  width="stretch")

        st_counts = api_df_f["Status"].value_counts().sort_index()
        def st_color(s): return "#3fb950" if s < 300 else "#d29922" if s < 400 else "#f85149"
        fig_st = go.Figure(go.Bar(x=[str(s) for s in st_counts.index], y=st_counts.values,
            marker_color=[st_color(s) for s in st_counts.index],
            text=st_counts.values, textposition="outside"))
        fig_st.update_layout(**CHART, title="HTTP Status Codes", height=280, showlegend=False)

        ep = api_df_f["Endpoint"].value_counts().head(15)
        fig_ep = go.Figure(go.Bar(x=ep.values, y=[e[:55] for e in ep.index], orientation="h",
            marker_color="#58a6ff", text=ep.values, textposition="outside"))
        fig_ep.update_layout(**CHART, title="Top 15 Endpoints",
                              height=max(300, len(ep)*32), showlegend=False)

        fig_cl = go.Figure(go.Pie(
            labels=api_df_f["Client"].value_counts().index.tolist(),
            values=api_df_f["Client"].value_counts().values.tolist(),
            marker_colors=PAL, hole=0.42))
        fig_cl.update_layout(**CHART, title="Requests by Client IP", height=300)

        col3, col4 = st.columns(2)
        with col3: st.plotly_chart(fig_st, width="stretch")
        with col4: st.plotly_chart(fig_cl, width="stretch")

        st.plotly_chart(fig_ep, width="stretch")

        errors_df = api_df_f[api_df_f["Status"] >= 400].sort_values("Timestamp", ascending=False).head(100)
        if not errors_df.empty:
            st.markdown(f"**{len(errors_df)} API error responses (4xx/5xx)**")
            st.dataframe(errors_df[["Timestamp","Method","Endpoint","Status","ResponseMs","Client"]],
                         width="stretch", hide_index=True)

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
        st.plotly_chart(fig_lv, width="stretch")

        errors = verb_df_f[verb_df_f["Level"].isin(["ERROR","CRITICAL","FATAL"])].copy()
        if not errors.empty:
            ev = errors.set_index("Timestamp").resample("1h").size().reset_index(name="errors")
            fe = go.Figure(go.Bar(x=ev["Timestamp"], y=ev["errors"],
                name="Errors/hr", marker_color="#f85149"))
            fe.update_layout(**CHART, title="Error Rate Over Time", height=250)
            st.plotly_chart(fe, width="stretch")

            st.markdown(f"**{len(errors)} ERROR entries (max 250 shown)**")
            st.dataframe(errors[["Timestamp","Log","Level","Message"]].head(250),
                         width="stretch", hide_index=True)

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
                              height=max(280, len(alarms_list)*50))
        st.plotly_chart(fig_tl, width="stretch")

        cnt = alrt_df_f[alrt_df_f["State"] == "asserted"]["Alarm"].value_counts()
        col1, col2 = st.columns(2)
        with col1:
            fig_cnt = go.Figure(go.Bar(x=cnt.values, y=cnt.index.tolist(), orientation="h",
                marker_color="#f85149", text=cnt.values, textposition="outside"))
            fig_cnt.update_layout(**CHART, title="Alert Occurrences",
                                   height=max(250, len(cnt)*38), showlegend=False)
            st.plotly_chart(fig_cnt, width="stretch")

        with col2:
            st.markdown("**Assert → Deassert Durations**")
            dur_rows = []
            for alarm in alarms_list:
                sub = alrt_df_f[alrt_df_f["Alarm"] == alarm].sort_values("Timestamp")
                last_on = None
                for _, r in sub.iterrows():
                    if r["State"] == "asserted":
                        last_on = r["Timestamp"]
                    elif r["State"] == "deasserted" and last_on is not None:
                        secs = (r["Timestamp"] - last_on).total_seconds()
                        dur_str = f"{int(secs//60)}m {int(secs%60)}s" if secs < 3600 else f"{secs/3600:.1f}h"
                        dur_rows.append({"Asserted At": str(last_on)[:19], "Alarm": alarm,
                                         "Deasserted At": str(r["Timestamp"])[:19], "Duration": dur_str})
                        last_on = None
            if dur_rows:
                st.dataframe(pd.DataFrame(dur_rows), width="stretch", hide_index=True)

        st.markdown(f"**Full alert log — {len(alrt_df_f)} entries**")
        st.dataframe(alrt_df_f, width="stretch", hide_index=True)

    if not evnt_df_f.empty:
        st.markdown(f"**event_log_1 — {len(evnt_df_f)} entries**")
        st.dataframe(evnt_df_f, width="stretch", hide_index=True)

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
                     width="stretch", hide_index=True)

    if configs:
        for fname, cfg in configs.items():
            with st.expander(fname):
                st.json(cfg)

    if not health and not configs:
        st.warning("No config/health data found.")
