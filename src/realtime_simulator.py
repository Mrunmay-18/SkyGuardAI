"""
src/realtime_simulator.py
SkyGuard AI — STEP 23: Real-Time Replay Simulator.

Replays historical AWS observations sequentially, with a configurable
delay, to simulate a live sensor stream for the hackathon demo.

IMPORTANT:
  - This file does NOT run ML. It does NOT detect anomalies.
  - It reads the ALREADY-COMPUTED alerts from outputs/alerts.json
    (produced by the frozen pipeline: Steps 11-22).
  - It only displays readings + alert cards in chronological order.
  - No Kafka / MQTT / WebSockets / cloud. Local replay only.

Usage:
    python src/realtime_simulator.py                 # default: 1.0s delay, windowed around alerts
    python src/realtime_simulator.py --delay 0.5     # faster
    python src/realtime_simulator.py --delay 2.0     # slower
    python src/realtime_simulator.py --full          # replay ALL rows (long)
    python src/realtime_simulator.py --limit 500     # first 500 rows only
    python src/realtime_simulator.py --no-wait       # instant, no delay (screen only)
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime


# ----------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------
OBS_CSV = "data/test_injected_aws.csv"
ALERTS_JSON = "outputs/alerts.json"

DEFAULT_DELAY_SECONDS = 1.0          # 1 second per reading for demo
WINDOW_BEFORE_ALERT = 5              # rows before each alert in windowed mode
WINDOW_AFTER_ALERT = 2               # rows after each alert in windowed mode

# ANSI colors (work in Windows Terminal, VS Code terminal, most Linux/macOS terminals)
RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[91m"
YELLOW = "\033[93m"
GREEN = "\033[92m"
CYAN = "\033[96m"
DIM = "\033[2m"


# ----------------------------------------------------------------------
# Loading
# ----------------------------------------------------------------------
def load_observations(path: str):
    """Load raw AWS observations CSV, parse timestamps, sort chronologically."""
    if not os.path.exists(path):
        print(f"{RED}[ERROR] Observations file not found: {path}{RESET}")
        print("        Expected at data/test_injected_aws.csv")
        sys.exit(1)

    import pandas as pd
    df = pd.read_csv(path)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values(["timestamp", "station_id"]).reset_index(drop=True)
    return df


def load_alerts(path: str) -> dict:
    """
    Load alerts.json and index them by (station_id, timestamp_string).

    Returns: dict {(station_id, timestamp_str): alert_dict}
    If the file is missing, returns {} (simulator will show NORMAL only).
    """
    if not os.path.exists(path):
        print(f"{YELLOW}[WARN] Alerts file not found: {path}{RESET}")
        print("       Simulator will run in NORMAL-only mode (no alerts shown).")
        return {}

    with open(path, "r", encoding="utf-8") as f:
        alerts_list = json.load(f)

    index = {}
    for a in alerts_list:
        key = (a["station_id"], str(a["timestamp"]))
        index[key] = a
    return index


# ----------------------------------------------------------------------
# Display
# ----------------------------------------------------------------------
def fmt_normal_line(row) -> str:
    """Format a single normal reading line."""
    ts = str(row["timestamp"])
    sid = row["station_id"]
    t = row["temperature"]
    p = row["pressure"]
    h = row["humidity"]
    return (
        f"{DIM}[{ts}]{RESET} {sid} | "
        f"{GREEN}NORMAL{RESET} | "
        f"T={t:6.2f} | P={p:7.2f} | H={h:5.2f}"
    )

def _wrap_text(text: str, width: int) -> list:
    """
    Wrap text to `width` characters at word boundaries.
    Returns a list of lines (no bullet prefix added here).
    """
    words = str(text).split()
    lines = []
    current = ""
    for w in words:
        if not current:
            current = w
        elif len(current) + 1 + len(w) <= width:
            current += " " + w
        else:
            lines.append(current)
            current = w
    if current:
        lines.append(current)
    return lines or [""]

def fmt_alert_card(alert: dict) -> str:
    """Format a multi-line alert card."""
    sid = alert.get("station_id", "?")
    ts = alert.get("timestamp", "?")
    atype = alert.get("anomaly_type", "Unknown")
    conf = alert.get("confidence", "?")
    sev = alert.get("severity", "?")
    t = alert.get("temperature", float("nan"))
    p = alert.get("pressure", float("nan"))
    h = alert.get("humidity", float("nan"))
    health = alert.get("sensor_health", "unknown")
    rec = alert.get("maintenance_recommendation", "")
    reasons = alert.get("reasons", []) or []

    # Severity color
    sev_color = {
        "Critical": RED + BOLD,
        "High": RED,
        "Medium": YELLOW,
        "Low": CYAN,
    }.get(sev, "")

    lines = []
    lines.append("")
    lines.append(f"{RED}{BOLD}╔══════════════════════════════════════════════════════════════════╗{RESET}")
    lines.append(f"{RED}{BOLD}║ 🚨 ANOMALY DETECTED                                              ║{RESET}")
    lines.append(f"{RED}{BOLD}╠══════════════════════════════════════════════════════════════════╣{RESET}")
    lines.append(f"║ Station:    {sid:<52} ║")
    lines.append(f"║ Time:       {ts:<52} ║")
    lines.append(f"║ Reading:    T={t:6.2f}°C  P={p:7.2f} hPa  RH={h:5.2f}%              ║")
    lines.append(f"║ Type:       {atype:<52} ║")
    lines.append(f"║ Confidence: {str(conf) + '/100':<52} ║")
    lines.append(f"║ Severity:   {sev_color}{sev:<52}{RESET} ║")
    lines.append(f"╠══════════════════════════════════════════════════════════════════╣{RESET}")
    lines.append(f"║ Reasons:                                                         ║")
    for r in reasons[:6]:
        wrapped = _wrap_text(str(r), width=58)
        # First line with bullet
        lines.append(f"║   • {wrapped[0]:<60} ║")
        # Continuation lines: indented, no bullet
        for cont in wrapped[1:]:
            lines.append(f"║     {cont:<60} ║")
            
    lines.append(f"╠══════════════════════════════════════════════════════════════════╣{RESET}")
    lines.append(f"║ Sensor health:  {health:<48} ║")

    # Recommendation — split long text onto continuation lines.
    rec_lines = [rec[i:i+48] for i in range(0, len(rec), 48)] or [""]
    for i, chunk in enumerate(rec_lines):
        prefix = "Recommendation: " if i == 0 else "                 "
        lines.append(f"║ {prefix}{chunk:<48} ║")

    # Self-healing corrected values.
    ct = alert.get("corrected_temperature")
    if ct is not None:
        cp = alert.get("corrected_pressure")
        ch = alert.get("corrected_humidity")
        cc = alert.get("correction_confidence", "?")
        lines.append(f"╠══════════════════════════════════════════════════════════════════╣{RESET}")
        lines.append(f"║ 🩹 Self-healing corrected reading:                              ║")
        lines.append(f"║    T={ct:6.2f}°C  P={cp:7.2f} hPa  RH={ch:5.2f}%              ║")
        lines.append(f"║    Confidence: {str(cc) + '/100':<48} ║")

    lines.append(f"{RED}{BOLD}╚══════════════════════════════════════════════════════════════════╝{RESET}")
    lines.append("")
    return "\n".join(lines)

# ----------------------------------------------------------------------
# Windowing
# ----------------------------------------------------------------------
def build_windowed_rows(df, alert_index: dict, before: int, after: int):
    """
    Build a reduced list of row indices: N rows before each alert,
    M rows after each alert. Deduplicate if windows overlap.

    Returns sorted list of positional indices into df.
    """
    if not alert_index:
        # No alerts -> take the first 200 rows so the demo shows something.
        return list(range(min(200, len(df))))

    # Map (station_id, ts_str) -> alert to positional index in df.
    keep = set()
    df_keys = list(zip(df["station_id"], df["timestamp"].astype(str)))
    key_to_pos = {k: i for i, k in enumerate(df_keys)}

    for alert_key in alert_index.keys():
        pos = key_to_pos.get(alert_key)
        if pos is None:
            continue
        lo = max(0, pos - before)
        hi = min(len(df), pos + after + 1)
        for i in range(lo, hi):
            keep.add(i)

    return sorted(keep)


# ----------------------------------------------------------------------
# Main loop
# ----------------------------------------------------------------------
def replay(df, alert_index, delay: float, window_rows=None, no_wait: bool = False):
    """
    Replay rows sequentially. If window_rows is provided, only iterate
    those positional indices. Else iterate the whole DataFrame.
    """
    if window_rows is not None:
        rows_to_play = df.iloc[window_rows]
    else:
        rows_to_play = df

    total = len(rows_to_play)
    alerts_shown = 0
    start = datetime.now()

    print(f"{BOLD}Starting replay...{RESET}\n")

    for i, (_, row) in enumerate(rows_to_play.iterrows(), start=1):
        sid = row["station_id"]
        ts_str = str(row["timestamp"])
        key = (sid, ts_str)

        # Is this row an alert?
        alert = alert_index.get(key)

        if alert is None:
            # Normal reading
            print(fmt_normal_line(row))
        else:
            # Alert card
            print(fmt_alert_card(alert))
            alerts_shown += 1

        # Progress indicator every 50 rows (for long replays)
        if i % 50 == 0:
            print(f"{DIM}  ... {i}/{total} rows replayed, {alerts_shown} alerts so far{RESET}")

        # Delay (skip on last row)
        if i < total and not no_wait:
            time.sleep(delay)

    elapsed = (datetime.now() - start).total_seconds()
    print()
    print("=" * 68)
    print(f"{BOLD}Replay complete.{RESET}")
    print(f"  Rows replayed:  {total}")
    print(f"  Alerts shown:   {alerts_shown}")
    print(f"  Elapsed:        {elapsed:.1f} seconds")
    print("=" * 68)


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------
def parse_args():
    p = argparse.ArgumentParser(description="SkyGuard AI Real-Time Replay Simulator")
    p.add_argument("--delay", type=float, default=DEFAULT_DELAY_SECONDS,
                   help=f"Delay between rows in seconds (default: {DEFAULT_DELAY_SECONDS})")
    p.add_argument("--full", action="store_true",
                   help="Replay ALL rows chronologically (long). Default is windowed around alerts.")
    p.add_argument("--limit", type=int, default=None,
                   help="Replay only the first N rows.")
    p.add_argument("--no-wait", action="store_true",
                   help="No delay between rows (instant screen output).")
    return p.parse_args()


def main():
    args = parse_args()

    print("=" * 68)
    print(f"{BOLD}=== Real-Time AWS Replay Simulator ==={RESET}")
    print("=" * 68)

    df = load_observations(OBS_CSV)
    alert_index = load_alerts(ALERTS_JSON)

    print(f"Rows available: {len(df)}")
    print(f"Alerts prepared: {len(alert_index)}")
    print(f"Replay delay: {args.delay} seconds")
    print(f"Mode: {'full' if args.full else ('first ' + str(args.limit) if args.limit else 'windowed around alerts')}")
    print()

    # Decide which rows to play
    if args.limit:
        window_rows = list(range(min(args.limit, len(df))))
    elif args.full:
        window_rows = None
    else:
        window_rows = build_windowed_rows(
            df, alert_index,
            before=WINDOW_BEFORE_ALERT,
            after=WINDOW_AFTER_ALERT,
        )
        print(f"Windowed replay: {len(window_rows)} rows (context around {len(alert_index)} alerts)")
        print()

    replay(df, alert_index, delay=args.delay, window_rows=window_rows, no_wait=args.no_wait)


if __name__ == "__main__":
    main()