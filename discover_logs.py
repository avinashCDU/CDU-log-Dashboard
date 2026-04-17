"""
CDU Log Discovery & Profiler
============================
Run this FIRST before the dashboard.
It scans your entire Gen3 CDU CW Data Center Logs folder,
reads samples from every file type, and prints a full report.

Usage:
    python discover_logs.py

Then paste or screenshot the output and share it — 
this tells us exactly what data is available for visualization.
"""

import os
import sys
import glob
import json
import re
import csv
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG — adjust ROOT_PATH if needed
# ─────────────────────────────────────────────────────────────────────────────
ONEDRIVE_CANDIDATES = [
    # Local test folder (Ellandale field logs)
    r"C:\Users\{user}\Desktop\OneDrive - Delta Electronics, Inc\2026\Projects\CW 140kW CDU in Field\Ellandale\Filed Issues Troubleshooting\GUI_CDU_Tool_v01\GUI_CDU_Tool_v01\02242026 Logs",
    # SharePoint synced paths (once synced via OneDrive)
    r"C:\Users\{user}\OneDrive - Delta Electronics\Gen3 CDU CW Data Center Logs",
    r"C:\Users\{user}\OneDrive\Gen3 CDU CW Data Center Logs",
    r"C:\Users\{user}\Delta Electronics\Gen3 CDU CW Data Center Logs",
    r"C:\Users\{user}\SharePoint\Gen3 CDU CW Data Center Logs",
]

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

RESET  = "\033[0m"
BOLD   = "\033[1m"
CYAN   = "\033[96m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
DIM    = "\033[2m"

def c(text, color): return f"{color}{text}{RESET}"
def hr(char="─", n=72): print(c(char * n, DIM))
def hdr(title):
    hr()
    print(c(f"  {title}", BOLD + CYAN))
    hr()

def find_root():
    user = os.environ.get("USERNAME", os.environ.get("USER", "user"))
    for tmpl in ONEDRIVE_CANDIDATES:
        p = tmpl.format(user=user)
        if os.path.isdir(p):
            return p
    return None

def human_size(n):
    for unit in ["B","KB","MB","GB"]:
        if n < 1024: return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"

def safe_read_lines(filepath, n=30):
    """Read up to n lines, trying multiple encodings."""
    for enc in ["utf-8", "utf-8-sig", "latin-1", "cp1252"]:
        try:
            with open(filepath, "r", encoding=enc, errors="replace") as f:
                lines = [f.readline() for _ in range(n)]
            return [l.rstrip("\n") for l in lines if l], enc
        except Exception:
            continue
    return [], "unknown"

def detect_log_format(lines):
    """Heuristic: what kind of log is this?"""
    if not lines: return "empty"
    sample = "\n".join(lines[:10])
    if re.search(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}.*ALERT', sample, re.I): return "alert_log"
    if re.search(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}.*EVENT', sample, re.I): return "event_log"
    if re.search(r'(GET|POST|PUT|DELETE|PATCH)\s+/', sample): return "api_access_log"
    if re.search(r'"(request|response|method|endpoint|status)"', sample): return "api_detail_json"
    if re.search(r'^\s*{', sample): return "json_log"
    if re.search(r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}', sample): return "timestamped_log"
    if re.search(r'(ERROR|WARN|INFO|DEBUG|FATAL)', sample, re.I): return "standard_log"
    return "unknown_text"

def parse_csv_profile(filepath):
    """Quick profile of a CSV: columns, row count, date range."""
    try:
        import pandas as pd
        df = pd.read_csv(filepath, nrows=5, low_memory=False)
        cols = df.columns.tolist()
        # count rows fast
        with open(filepath, "rb") as f:
            row_count = sum(1 for _ in f) - 1
        # detect timestamp col
        ts_col = next((c for c in cols if "time" in c.lower() or "date" in c.lower()), None)
        ts_info = ""
        if ts_col:
            df_full = pd.read_csv(filepath, usecols=[ts_col], low_memory=False)
            ts_series = pd.to_datetime(df_full[ts_col], errors="coerce").dropna()
            if not ts_series.empty:
                ts_info = f"{ts_series.min()} → {ts_series.max()}"
        return {"rows": row_count, "cols": len(cols), "columns": cols,
                "timestamp_range": ts_info}
    except Exception as e:
        return {"error": str(e)}

def extract_log_timestamps(lines):
    """Pull first and last timestamp from log lines."""
    ts_pattern = re.compile(
        r'(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{4})?)'
    )
    stamps = []
    for line in lines:
        m = ts_pattern.search(line)
        if m: stamps.append(m.group(1))
    return stamps[0] if stamps else None, stamps[-1] if len(stamps) > 1 else None

def extract_log_levels(lines):
    """Count occurrences of log levels."""
    levels = defaultdict(int)
    pattern = re.compile(r'\b(ERROR|WARN(?:ING)?|INFO|DEBUG|FATAL|CRITICAL|ALERT)\b', re.I)
    for line in lines:
        for m in pattern.findall(line):
            levels[m.upper()] += 1
    return dict(levels)

def profile_log_file(filepath):
    """Full profile of a .log / .txt file."""
    size = os.path.getsize(filepath)
    lines_sample, enc = safe_read_lines(filepath, 50)
    fmt = detect_log_format(lines_sample)
    ts_first, ts_last = extract_log_timestamps(lines_sample)
    levels = extract_log_levels(lines_sample)
    # count total lines fast
    try:
        with open(filepath, "rb") as f:
            total_lines = sum(1 for _ in f)
    except: total_lines = "?"
    return {
        "size": size, "encoding": enc, "format": fmt,
        "total_lines": total_lines, "sample_lines": lines_sample[:8],
        "ts_first": ts_first, "ts_last": ts_last,
        "log_levels": levels,
    }

# ─────────────────────────────────────────────────────────────────────────────
# MAIN DISCOVERY
# ─────────────────────────────────────────────────────────────────────────────

def discover(root):
    """Walk the tree and collect all files grouped by DC → Unit → type."""
    tree = {}   # dc → unit → [file_info]
    all_files = []

    for dc in sorted(os.listdir(root)):
        dc_path = os.path.join(root, dc)
        if not os.path.isdir(dc_path): continue
        tree[dc] = {}

        # Walk all subdirs under dc
        for dirpath, dirnames, filenames in os.walk(dc_path):
            dirnames.sort()
            # Figure out "unit" label from path
            rel = os.path.relpath(dirpath, dc_path)
            unit = rel.split(os.sep)[0] if rel != "." else "(root)"

            for fname in sorted(filenames):
                fpath = os.path.join(dirpath, fname)
                ext   = Path(fname).suffix.lower()
                stem  = Path(fname).stem.lower()
                size  = os.path.getsize(fpath)

                entry = {
                    "dc": dc, "unit": unit, "dir": dirpath,
                    "filename": fname, "path": fpath,
                    "ext": ext, "size": size,
                }
                tree[dc].setdefault(unit, []).append(entry)
                all_files.append(entry)

    return tree, all_files

def run():
    print()
    print(c("╔══════════════════════════════════════════════════════════════════╗", CYAN))
    print(c("║   CDU Log Discovery & Profiler                                   ║", CYAN + BOLD))
    print(c("║   Gen3 CDU CW Data Center Logs                                   ║", CYAN))
    print(c("╚══════════════════════════════════════════════════════════════════╝", CYAN))
    print()

    # ── Find root ─────────────────────────────────────────────────────────────
    root = find_root()
    if not root:
        print(c("❌  Could not auto-detect OneDrive root.", RED))
        print("Please edit this script and set ROOT_PATH manually:")
        print(r'  root = r"C:\Users\you\OneDrive - Delta Electronics\Gen3 CDU CW Data Center Logs"')
        sys.exit(1)

    print(c(f"✅  Root found: {root}", GREEN))
    print()

    # ── Walk tree ─────────────────────────────────────────────────────────────
    tree, all_files = discover(root)

    hdr("📁  FOLDER STRUCTURE OVERVIEW")
    total_size = sum(f["size"] for f in all_files)
    print(f"  Total files : {c(str(len(all_files)), BOLD)}")
    print(f"  Total size  : {c(human_size(total_size), BOLD)}")
    print()

    for dc, units in tree.items():
        dc_files = [f for f in all_files if f["dc"] == dc]
        dc_size  = sum(f["size"] for f in dc_files)
        print(f"  {c('▶ ' + dc, BOLD + YELLOW)}  ({len(dc_files)} files, {human_size(dc_size)})")
        for unit, files in units.items():
            u_size = sum(f["size"] for f in files)
            print(f"      {c(unit, CYAN)}  — {len(files)} files, {human_size(u_size)}")
            # Group by base name pattern
            by_type = defaultdict(list)
            for f in files:
                key = re.sub(r'\.\d+$', '', f["filename"])  # strip .1 .2 etc
                by_type[key].append(f)
            for base, grp in sorted(by_type.items()):
                sizes = [human_size(g["size"]) for g in grp]
                print(f"        {DIM}├─{RESET} {base}  ×{len(grp)}  [{', '.join(sizes[:4])}{'...' if len(sizes)>4 else ''}]")
        print()

    # ── File type summary ─────────────────────────────────────────────────────
    hdr("📊  FILE TYPE BREAKDOWN")
    by_ext = defaultdict(list)
    for f in all_files:
        by_ext[f["ext"] or "(no ext)"].append(f)
    for ext, files in sorted(by_ext.items(), key=lambda x: -len(x[1])):
        total = sum(f["size"] for f in files)
        ext_label = f"{ext or '(none)':<20}"
        print(f"  {c(ext_label, BOLD)}  {len(files):4d} files   {human_size(total):>10s}")
    print()

    # ── Deep profile: sample each unique file type ─────────────────────────────
    hdr("🔍  DEEP PROFILE — SAMPLE OF EACH FILE TYPE")

    # Pick representative files: one of each base name pattern per DC
    seen_patterns = set()
    to_profile = []
    for f in all_files:
        pattern = re.sub(r'\.\d+$', '', f["filename"])
        key = (f["dc"], pattern)
        if key not in seen_patterns:
            seen_patterns.add(key)
            to_profile.append(f)

    for f in to_profile:
        ext  = f["ext"].lower()
        size = human_size(f["size"])
        rel  = os.path.relpath(f["path"], root)
        print()
        print(c(f"  FILE: {rel}  ({size})", BOLD))

        if ext == ".csv":
            prof = parse_csv_profile(f["path"])
            if "error" in prof:
                print(f"    {c('Error:', RED)} {prof['error']}")
            else:
                print(f"    Rows      : {c(str(prof['rows']), GREEN)}")
                print(f"    Columns   : {c(str(prof['cols']), GREEN)}")
                print(f"    Time range: {prof['timestamp_range'] or 'N/A'}")
                print(f"    Columns   :")
                # group columns by category
                cols = prof["columns"]
                for i in range(0, len(cols), 4):
                    chunk = cols[i:i+4]
                    print(f"      {DIM}{', '.join(chunk)}{RESET}")

        elif ext in [".log", ".txt", ".1", ".2", ".3", ".4", ".5", ""]:
            prof = profile_log_file(f["path"])
            print(f"    Format     : {c(prof['format'], YELLOW)}")
            print(f"    Total lines: {prof['total_lines']}")
            print(f"    Encoding   : {prof['encoding']}")
            print(f"    First TS   : {prof['ts_first'] or 'not detected'}")
            print(f"    Last TS    : {prof['ts_last'] or 'not detected'}")
            if prof["log_levels"]:
                lvl_str = "  ".join(f"{k}:{v}" for k,v in sorted(prof["log_levels"].items()))
                print(f"    Log levels : {c(lvl_str, YELLOW)}")
            print(f"    {c('Sample lines:', DIM)}")
            for line in prof["sample_lines"][:6]:
                print(f"      {DIM}│{RESET} {line[:120]}")

        elif ext == ".json":
            lines, _ = safe_read_lines(f["path"], 5)
            print(f"    {c('Sample:', DIM)}")
            for line in lines[:4]:
                print(f"      {DIM}│{RESET} {line[:120]}")

        else:
            lines, enc = safe_read_lines(f["path"], 5)
            print(f"    Encoding: {enc}")
            for line in lines[:4]:
                print(f"      {DIM}│{RESET} {line[:120]}")

    # ── Visualization opportunities summary ───────────────────────────────────
    hdr("💡  VISUALIZATION OPPORTUNITIES DETECTED")

    has_csv    = any(f["ext"] == ".csv" for f in all_files)
    has_alert  = any("alert" in f["filename"].lower() for f in all_files)
    has_event  = any("event" in f["filename"].lower() for f in all_files)
    has_api_a  = any("api_access" in f["filename"].lower() for f in all_files)
    has_api_d  = any("api_detail" in f["filename"].lower() for f in all_files)

    checks = [
        (has_csv,   "system_log*.csv",    "Time-series sensor charts (temp, pressure, flow, pumps, power)"),
        (has_alert, "alert_log*.log",     "Alarm timeline, severity breakdown, alert frequency"),
        (has_event, "event_log*.log",     "System event timeline, event type distribution"),
        (has_api_a, "api_access.log",     "API call volume, HTTP status codes, endpoint usage"),
        (has_api_d, "api_detail.log",     "API request/response detail, error analysis"),
    ]
    for found, name, desc in checks:
        icon = c("✅", GREEN) if found else c("❌", RED)
        name_label = f"{name:<30}"
        print(f"  {icon}  {c(name_label, BOLD)} → {desc}")

    print()
    print(c("═" * 72, DIM))
    print(c("  ✔  Discovery complete. Share this output to build the full dashboard.", GREEN + BOLD))
    print(c("═" * 72, DIM))
    print()

    # ── Save report to file too ────────────────────────────────────────────────
    report_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "discovery_report.txt")
    try:
        # Simple summary to file
        lines_out = [
            "CDU Log Discovery Report",
            f"Generated: {datetime.now().isoformat()}",
            f"Root: {root}",
            "",
            "=== FOLDER STRUCTURE ===",
        ]
        for dc, units in tree.items():
            dc_files = [f for f in all_files if f["dc"] == dc]
            lines_out.append(f"\n[{dc}]  {len(dc_files)} files")
            for unit, files in units.items():
                lines_out.append(f"  Unit: {unit}  ({len(files)} files)")
                for fi in files:
                    lines_out.append(f"    {fi['filename']}  {human_size(fi['size'])}")

        lines_out += ["", "=== FILE TYPE BREAKDOWN ==="]
        for ext, files in sorted(by_ext.items(), key=lambda x: -len(x[1])):
            lines_out.append(f"  {ext or '(none)':20s}  {len(files)} files  {human_size(sum(f['size'] for f in files))}")

        with open(report_path, "w", encoding="utf-8") as rpt:
            rpt.write("\n".join(lines_out))
        print(f"  Report also saved to: {c(report_path, CYAN)}")
    except Exception as e:
        print(f"  (Could not save report file: {e})")

    print()

if __name__ == "__main__":
    run()
