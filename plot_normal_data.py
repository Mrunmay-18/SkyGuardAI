"""
plot_normal_data.py
SkyGuard AI - Visual sanity check of the synthetic normal AWS data.

Reads data/normal_aws_data.csv and produces four PNG plots inside data/plots/:
  1. temperature_vs_time_aws01.png         - Temperature vs Time for AWS_01
  2. pressure_vs_time_aws01.png            - Pressure    vs Time for AWS_01
  3. humidity_vs_time_aws01.png            - Humidity    vs Time for AWS_01
  4. temperature_comparison_all_stations.png - Temperature for all 5 stations

This script does NOT modify the CSV, does NOT create any anomaly data, and
does NOT build any ML model or dashboard code.
"""

import os
import matplotlib
matplotlib.use("Agg")  # headless backend - no display required (e.g. on servers)
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import matplotlib.dates as mdates
import pandas as pd


# ----------------------------------------------------------------------
# Font setup: register Noto Sans SC + DejaVu Sans for robust per-glyph
# fallback (matplotlib 3.9+ falls back across the font.sans-serif list).
# Even though this script's labels are in English, registering both
# fonts keeps the plots robust across environments.
# ----------------------------------------------------------------------
for font_path in [
    "/usr/share/fonts/truetype/chinese/NotoSansSC-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]:
    if os.path.exists(font_path):
        fm.fontManager.addfont(font_path)

plt.rcParams["font.sans-serif"] = ["Noto Sans SC", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False  # ASCII minus sign (not U+2212)


# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------
DATA_PATH = "data/normal_aws_data.csv"
PLOTS_DIR = "data/plots"
FOCUS_STATION = "AWS_01"  # station plotted clearly in single-variable plots


def ensure_dir(path):
    """Create a directory if it does not exist (does NOT touch the CSV)."""
    os.makedirs(path, exist_ok=True)


def load_data(path):
    """Read the normal AWS CSV with `timestamp` parsed as datetime."""
    return pd.read_csv(path, parse_dates=["timestamp"])


def _style_time_axis(ax):
    """
    Format and rotate the x-axis dates cleanly.

    Using matplotlib.dates locators/formatters + tick labelrotation works
    well with constrained_layout (unlike fig.autofmt_xdate, which adjusts
    figure margins and conflicts with constrained_layout).
    """
    # Show a tick every 3 days so the labels don't overlap.
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=3))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    ax.tick_params(axis="x", labelrotation=30)


def plot_single_station_variable(df, station_id, variable, ylabel, title, out_path):
    """Plot one variable vs time for a single station, clearly."""
    sub = df[df["station_id"] == station_id].sort_values("timestamp")

    # constrained_layout=True manages spacing; do NOT also call tight_layout
    # or pass bbox_inches='tight' to savefig (they would conflict).
    fig, ax = plt.subplots(figsize=(12, 4.5), constrained_layout=True)
    ax.plot(sub["timestamp"], sub[variable],
            color="tab:blue", linewidth=0.9, alpha=0.9)
    ax.set_title(title)
    ax.set_xlabel("Time")
    ax.set_ylabel(ylabel)
    ax.grid(True, which="major", linestyle="--", alpha=0.4)
    _style_time_axis(ax)
    fig.savefig(out_path, dpi=130)
    plt.close(fig)


def plot_temperature_comparison(df, out_path):
    """Plot temperature vs time for all 5 stations on a single axis."""
    fig, ax = plt.subplots(figsize=(13, 5.5), constrained_layout=True)
    stations = sorted(df["station_id"].unique())
    cmap = plt.get_cmap("tab10")  # 10 distinct, perceptually distinct colors
    for idx, sid in enumerate(stations):
        sub = df[df["station_id"] == sid].sort_values("timestamp")
        ax.plot(sub["timestamp"], sub["temperature"],
                color=cmap(idx), linewidth=0.8, alpha=0.85, label=sid)

    ax.set_title("Temperature vs Time - All Stations Comparison")
    ax.set_xlabel("Time")
    ax.set_ylabel("Temperature (°C)")
    ax.grid(True, which="major", linestyle="--", alpha=0.4)
    # Place legend OUTSIDE the plot area so it never covers data points.
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0),
              title="Station", frameon=False)
    _style_time_axis(ax)
    fig.savefig(out_path, dpi=130)
    plt.close(fig)


def main():
    ensure_dir(PLOTS_DIR)

    df = load_data(DATA_PATH)
    print(f"Loaded {len(df)} rows from {DATA_PATH}")
    print(f"Stations : {sorted(df['station_id'].unique().tolist())}")
    print(f"Date range: {df['timestamp'].min()} -> {df['timestamp'].max()}")

    # 1) Temperature vs Time (single station, clearly visible)
    p1 = os.path.join(PLOTS_DIR, f"temperature_vs_time_{FOCUS_STATION.lower()}.png")
    plot_single_station_variable(
        df, FOCUS_STATION, "temperature", "Temperature (°C)",
        f"Temperature vs Time - {FOCUS_STATION}", p1)

    # 2) Pressure vs Time (single station)
    p2 = os.path.join(PLOTS_DIR, f"pressure_vs_time_{FOCUS_STATION.lower()}.png")
    plot_single_station_variable(
        df, FOCUS_STATION, "pressure", "Pressure (hPa)",
        f"Pressure vs Time - {FOCUS_STATION}", p2)

    # 3) Humidity vs Time (single station)
    p3 = os.path.join(PLOTS_DIR, f"humidity_vs_time_{FOCUS_STATION.lower()}.png")
    plot_single_station_variable(
        df, FOCUS_STATION, "humidity", "Relative Humidity (%)",
        f"Humidity vs Time - {FOCUS_STATION}", p3)

    # 4) Comparison: Temperature across all 5 stations
    p4 = os.path.join(PLOTS_DIR, "temperature_comparison_all_stations.png")
    plot_temperature_comparison(df, p4)

    # ----- Short summary -----
    print()
    print("=" * 60)
    print("SkyGuard AI - Normal data plot generation complete")
    print("=" * 60)
    print(f"Generated 4 plot(s) in: {PLOTS_DIR}")
    for p in [p1, p2, p3, p4]:
        print(f"  - {p}")
    print()
    print("What to look for (sanity check):")
    print("  * Temperature: clear daily cycle - low at night, peak in afternoon.")
    print("  * Pressure: smooth variation, no sudden jumps.")
    print("  * Humidity: inverse to temperature (higher at night, lower midday).")
    print("  * Comparison: 5 stations track together but not identically.")


if __name__ == "__main__":
    main()