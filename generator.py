"""
generator.py
SkyGuard AI - Synthetic Normal AWS Data Generator

Generates synthetic NORMAL (non-anomalous) Automatic Weather Station (AWS)
observations for 5 stations over 30 days at 15-minute intervals.

NOTE: This is SYNTHETIC data for a hackathon prototype. It does NOT represent
real-world climate for any specific city. No anomalies are injected and there
are no ground-truth labels (no `is_anomaly`, `anomaly_type`, etc.).
"""

import os
import numpy as np
import pandas as pd


# ----------------------------------------------------------------------
# Reproducibility: fix the global random seed so re-runs produce identical
# output. All subsequent np.random.* calls draw from this seeded stream.
# ----------------------------------------------------------------------
RANDOM_SEED = 42
np.random.seed(RANDOM_SEED)


# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------
STATIONS = ["AWS_01", "AWS_02", "AWS_03", "AWS_04", "AWS_05"]

START_TIMESTAMP = "2026-01-01 00:00:00"
DAYS = 30
OBS_PER_DAY = 96                 # 15-minute interval => 24 * 4 = 96 per day
TOTAL_OBS_PER_STATION = DAYS * OBS_PER_DAY   # 2880

OUTPUT_DIR = "data"
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "normal_aws_data.csv")


# ----------------------------------------------------------------------
# Per-station baseline conditions.
#
# Each station has slightly different baseline temperature, humidity, and
# pressure, plus slightly different diurnal amplitudes.
#
# AWS_01 and AWS_02 are designed to act like "nearby" stations with very
# similar baselines. AWS_04 and AWS_05 are another nearby pair. AWS_03 is
# a slightly warmer / drier outlier. This makes the 5 stations behave like
# a small regional network rather than 5 fully independent sites.
# ----------------------------------------------------------------------
STATION_PROFILES = {
    "AWS_01": {"t_base": 22.0, "h_base": 60.0, "p_base": 1012.0,
               "t_amp": 6.0,  "h_amp": 12.0},
    "AWS_02": {"t_base": 22.5, "h_base": 59.0, "p_base": 1011.5,
               "t_amp": 6.2,  "h_amp": 11.5},   # near AWS_01
    "AWS_03": {"t_base": 25.0, "h_base": 55.0, "p_base": 1010.0,
               "t_amp": 7.0,  "h_amp": 14.0},   # warmer / drier
    "AWS_04": {"t_base": 20.0, "h_base": 65.0, "p_base": 1014.0,
               "t_amp": 5.5,  "h_amp": 10.0},   # cooler / wetter
    "AWS_05": {"t_base": 21.0, "h_base": 62.0, "p_base": 1013.0,
               "t_amp": 5.8,  "h_amp": 11.0},   # near AWS_04
}


def generate_timestamps(start, n_obs, freq_min=15):
    """Build a pandas DatetimeIndex of n_obs timestamps spaced freq_min apart."""
    return pd.date_range(start=start, periods=n_obs, freq=f"{freq_min}min")


def mean_reverting_walk(n, step_scale, decay):
    """
    Smooth, bounded random walk (AR(1)-like).

    Each value is a small step from the previous one, gently pulled back
    toward zero so the walk does not drift unbounded over 30 days. This
    produces smooth variation over time without sudden jumps.
    """
    steps = np.random.normal(0, step_scale, size=n)
    walk = np.zeros(n)
    val = 0.0
    for i in range(n):
        val = (1.0 - decay) * val + steps[i]
        walk[i] = val
    return walk


def diurnal_temperature(ts, t_base, t_amp, noise_scale=0.4):
    """
    Build a realistic diurnal temperature curve.

    - Cosine phased to peak around 14:30 (afternoon) and trough around
      02:30 (pre-dawn). This gives lower temps at night, rising in the
      morning, peak in the afternoon, falling in the evening.
    - A slow mean-reverting walk adds multi-day variation without sudden
      jumps.
    - Small Gaussian noise adds fine variation so values are not perfectly
      mathematical.
    """
    # Fractional hour of day (0..24) for each timestamp.
    hour_of_day = (ts.hour + ts.minute / 60.0).to_numpy()

    peak_hour = 14.5  # afternoon peak
    phase = 2.0 * np.pi * (hour_of_day - peak_hour) / 24.0
    diurnal = t_amp * np.cos(phase)   # +t_amp at 14:30, -t_amp at 02:30

    n = len(ts)
    slow = mean_reverting_walk(n, step_scale=0.4, decay=0.01)   # smooth drift
    noise = np.random.normal(0, noise_scale, size=n)            # fine variation

    return t_base + diurnal + slow + noise


def diurnal_humidity(ts, h_base, h_amp, temperature, t_base, noise_scale=2.0):
    """
    Build humidity with a roughly inverse relationship to temperature,
    but NOT perfectly inverse:

    - Has its own diurnal cycle (peak pre-dawn, trough afternoon).
    - Loosely coupled to temperature (~30% of temperature deviation,
      inverted). The coupling is intentionally partial so the
      relationship is real but not mathematical.
    - Additional slow walk + fast noise that are NOT temperature-driven.
    """
    hour_of_day = (ts.hour + ts.minute / 60.0).to_numpy()

    peak_hour = 4.0  # humidity peaks pre-dawn
    phase = 2.0 * np.pi * (hour_of_day - peak_hour) / 24.0
    diurnal = h_amp * np.cos(phase)

    # Loose partial inverse coupling to temperature.
    inverse_coupling = -0.3 * (temperature - t_base)

    n = len(ts)
    slow = mean_reverting_walk(n, step_scale=0.3, decay=0.01)
    noise = np.random.normal(0, noise_scale, size=n)

    humidity = h_base + diurnal + inverse_coupling + slow + noise
    # Clip to physically plausible range for relative humidity (%).
    return np.clip(humidity, 5.0, 99.0)


def smooth_pressure(ts, p_base, step_scale=0.15, noise_scale=0.2):
    """
    Pressure varies smoothly over time with no sudden jumps.

    Implemented as a mean-reverting random walk (so it stays near p_base
    over 30 days) plus tiny Gaussian noise.
    """
    n = len(ts)
    slow = mean_reverting_walk(n, step_scale=step_scale, decay=0.005)
    noise = np.random.normal(0, noise_scale, size=n)
    return p_base + slow + noise


def generate_station_data(station_id, timestamps):
    """Build one station's full 30-day dataframe."""
    prof = STATION_PROFILES[station_id]

    temperature = diurnal_temperature(timestamps, prof["t_base"], prof["t_amp"])
    humidity = diurnal_humidity(timestamps, prof["h_base"], prof["h_amp"],
                                temperature, prof["t_base"])
    pressure = smooth_pressure(timestamps, prof["p_base"])

    df = pd.DataFrame({
        "timestamp": timestamps,
        "station_id": station_id,
        "temperature": np.round(temperature, 2),
        "pressure": np.round(pressure, 2),
        "humidity": np.round(humidity, 2),
    })
    return df


def main():
    # Create output directory if it does not exist.
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Shared timestamp grid for all stations.
    timestamps = generate_timestamps(START_TIMESTAMP, TOTAL_OBS_PER_STATION)

    # Build data for all stations, then concatenate.
    frames = [generate_station_data(sid, timestamps) for sid in STATIONS]
    df = pd.concat(frames, ignore_index=True)

    # Sort by timestamp then station_id so the CSV reads chronologically
    # and, within each timestamp, stations appear in a stable order.
    df = df.sort_values(["timestamp", "station_id"]).reset_index(drop=True)

    # Save to CSV (no extra index column).
    df.to_csv(OUTPUT_PATH, index=False)

    # ----- Print useful summary information -----
    print("=" * 60)
    print("SkyGuard AI - Synthetic Normal AWS Data Generation")
    print("=" * 60)
    print(f"Output file       : {OUTPUT_PATH}")
    print(f"Number of rows    : {len(df)}")
    print(f"Number of stations: {df['station_id'].nunique()}")
    print(f"Stations          : {sorted(df['station_id'].unique().tolist())}")
    print(f"Date range        : {df['timestamp'].min()} -> {df['timestamp'].max()}")
    print(f"Rows per station  : {df.groupby('station_id').size().to_dict()}")
    print(f"Random seed       : {RANDOM_SEED}")
    print("-" * 60)
    print("First few rows:")
    print(df.head(10).to_string(index=False))
    print("-" * 60)
    print("Per-station summary (mean / std):")
    summary = (df.groupby("station_id")[["temperature", "pressure", "humidity"]]
                 .agg(["mean", "std"]).round(2))
    print(summary.to_string())


if __name__ == "__main__":
    main()