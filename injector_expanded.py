"""
injector_expanded.py
SkyGuard AI — Expanded anomaly injector.

Reads data/normal_aws_data.csv, injects 40+ instances of each anomaly
type across all 5 stations, and writes data/test_expanded_aws.csv.

Does NOT modify the original test file. Does NOT retrain any model.
Ground truth columns (is_anomaly, anomaly_type, injected_parameter)
are preserved for evaluation only.
"""

import os
import sys
from dataclasses import dataclass

import numpy as np
import pandas as pd


# ----------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------
INPUT_PATH = "data/normal_aws_data.csv"
OUTPUT_PATH = "data/test_expanded_aws.csv"
RANDOM_SEED = 42

STATIONS = ["AWS_01", "AWS_02", "AWS_03", "AWS_04", "AWS_05"]
OBS_PER_DAY = 96  # 15-min cadence


@dataclass
class InjectionConfig:
    """How many instances of each anomaly type to inject."""
    temperature_spike: int = 40
    temperature_drop: int = 40
    frozen_sensor: int = 40
    calibration_drift: int = 10   # reduce to balance the eval set
    power_failure: int = 40
    multivariate_inconsistency: int = 40
    missing_data: int = 40
    normal_weather_event: int = 80  # not labeled as anomaly


# ----------------------------------------------------------------------
# Utilities
# ----------------------------------------------------------------------
def load_normal_data(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Input not found: {path}. Run generator.py first."
        )
    df = pd.read_csv(path)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


def init_ground_truth(df: pd.DataFrame) -> pd.DataFrame:
    if "is_anomaly" not in df.columns:
        df["is_anomaly"] = 0
    if "anomaly_type" not in df.columns:
        df["anomaly_type"] = "normal"
    if "injected_parameter" not in df.columns:
        df["injected_parameter"] = "none"
    return df


def get_station_block(df, station_id, day_offset, length, jitter_min=0):
    """
    Return row indices for a contiguous block of `length` observations
    starting at day_offset (0-indexed) plus jitter_min minutes.
    """
    station_df = df[df["station_id"] == station_id].reset_index()
    start_idx = day_offset * OBS_PER_DAY + (jitter_min // 15)
    end_idx = start_idx + length
    if end_idx > len(station_df):
        end_idx = len(station_df)
        start_idx = max(0, end_idx - length)
    return station_df.iloc[start_idx:end_idx]["index"].tolist()


# ----------------------------------------------------------------------
# Anomaly injectors
# ----------------------------------------------------------------------
def inject_temperature_spike(df, station_id, day_offset, length=5, jitter_min=0):
    idxs = get_station_block(df, station_id, day_offset, length, jitter_min)
    if not idxs:
        return 0
    # Add a spike to the middle reading
    mid = idxs[len(idxs) // 2]
    df.loc[mid, "temperature"] = float(df.loc[mid, "temperature"]) + 20.0
    df.loc[mid, "is_anomaly"] = 1
    df.loc[mid, "anomaly_type"] = "temperature_spike"
    df.loc[mid, "injected_parameter"] = "temperature"
    return 1


def inject_temperature_drop(df, station_id, day_offset, length=5, jitter_min=0):
    idxs = get_station_block(df, station_id, day_offset, length, jitter_min)
    if not idxs:
        return 0
    mid = idxs[len(idxs) // 2]
    df.loc[mid, "temperature"] = float(df.loc[mid, "temperature"]) - 15.0
    df.loc[mid, "is_anomaly"] = 1
    df.loc[mid, "anomaly_type"] = "temperature_drop"
    df.loc[mid, "injected_parameter"] = "temperature"
    return 1


def inject_frozen_sensor(df, station_id, day_offset, length=24, jitter_min=0):
    idxs = get_station_block(df, station_id, day_offset, length, jitter_min)
    if len(idxs) < 12:
        return 0
    # Freeze to the first value in the block
    freeze_val = float(df.loc[idxs[0], "temperature"])
    for i in idxs:
        df.loc[i, "temperature"] = freeze_val
        df.loc[i, "is_anomaly"] = 1
        df.loc[i, "anomaly_type"] = "frozen_sensor"
        df.loc[i, "injected_parameter"] = "temperature"
    return len(idxs)


def inject_calibration_drift(df, station_id, day_offset, length=96, max_bias=4.0, jitter_min=0):
    idxs = get_station_block(df, station_id, day_offset, length, jitter_min)
    if not idxs:
        return 0
    # Linear ramp 0 → max_bias over the block
    bias = np.linspace(0.0, max_bias, len(idxs))
    for i, b in zip(idxs, bias):
        df.loc[i, "temperature"] = float(df.loc[i, "temperature"]) + b
        df.loc[i, "is_anomaly"] = 1
        df.loc[i, "anomaly_type"] = "calibration_drift"
        df.loc[i, "injected_parameter"] = "temperature"
    return len(idxs)


def inject_power_failure(df, station_id, day_offset, length=4, jitter_min=0):
    idxs = get_station_block(df, station_id, day_offset, length, jitter_min)
    if not idxs:
        return 0
    for i in idxs:
        df.loc[i, "temperature"] = 0.0
        df.loc[i, "pressure"] = 0.0
        df.loc[i, "humidity"] = 0.0
        df.loc[i, "is_anomaly"] = 1
        df.loc[i, "anomaly_type"] = "power_failure"
        df.loc[i, "injected_parameter"] = "all"
    return len(idxs)


def inject_multivariate_inconsistency(df, station_id, day_offset, length=6, jitter_min=0):
    idxs = get_station_block(df, station_id, day_offset, length, jitter_min)
    if not idxs:
        return 0
    # Humidity spike without corresponding T/P change
    for i in idxs:
        df.loc[i, "humidity"] = min(100.0, float(df.loc[i, "humidity"]) + 30.0)
        df.loc[i, "is_anomaly"] = 1
        df.loc[i, "anomaly_type"] = "multivariate_inconsistency"
        df.loc[i, "injected_parameter"] = "humidity"
    return len(idxs)


def inject_missing_data(df, station_id, day_offset, length=12, jitter_min=0):
    # Missing data = rows deleted. We'll mark this via a flag on the
    # preceding row, since the actual rows won't exist in the output.
    # For evaluation simplicity, we DON'T delete rows in this version —
    # we just mark them as a special anomaly type.
    idxs = get_station_block(df, station_id, day_offset, length, jitter_min)
    if not idxs:
        return 0
    for i in idxs:
        df.loc[i, "is_anomaly"] = 1
        df.loc[i, "anomaly_type"] = "missing_data"
        df.loc[i, "injected_parameter"] = "all"
    return len(idxs)


def inject_normal_weather_event(df, station_ids, day_offset, length=48,
                                temp_shift=-3.0, jitter_min=0):
    """
    Inject a regional weather event across multiple stations — NOT labeled
    as anomaly. Tests false alarm rate on genuine weather.
    """
    total = 0
    for sid in station_ids:
        idxs = get_station_block(df, sid, day_offset, length, jitter_min)
        for i in idxs:
            df.loc[i, "temperature"] = float(df.loc[i, "temperature"]) + temp_shift
            # Do NOT set is_anomaly — this is genuine weather
            total += 1
    return total


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------
def main():
    if not os.path.exists(INPUT_PATH):
        raise FileNotFoundError(f"Input not found: {INPUT_PATH}")

    print(f"Loading {INPUT_PATH}...")
    df = load_normal_data(INPUT_PATH)
    df = init_ground_truth(df)

    print(f"Loaded {len(df)} rows across {df['station_id'].nunique()} stations")

    cfg = InjectionConfig()
    rng = np.random.default_rng(RANDOM_SEED)
    counts = {}

    # ---- Temperature spikes ----
    n = 0
    for i in range(cfg.temperature_spike):
        sid = STATIONS[i % len(STATIONS)]
        day = 1 + (i // len(STATIONS)) * 2  # spread across days
        n += inject_temperature_spike(df, sid, day_offset=day,
                                       jitter_min=int(rng.integers(0, 6)) * 15)
    counts["temperature_spike"] = n

    # ---- Temperature drops ----
    n = 0
    for i in range(cfg.temperature_drop):
        sid = STATIONS[i % len(STATIONS)]
        day = 3 + (i // len(STATIONS)) * 2
        n += inject_temperature_drop(df, sid, day_offset=day,
                                      jitter_min=int(rng.integers(0, 6)) * 15)
    counts["temperature_drop"] = n

    # ---- Frozen sensor ----
    n = 0
    for i in range(cfg.frozen_sensor):
        sid = STATIONS[i % len(STATIONS)]
        day = 5 + (i // len(STATIONS)) * 3
        n += inject_frozen_sensor(df, sid, day_offset=day, length=24,
                                   jitter_min=int(rng.integers(0, 6)) * 15)
    counts["frozen_sensor"] = n

    # ---- Calibration drift ----
    n = 0
    for i in range(cfg.calibration_drift):
        sid = STATIONS[i % len(STATIONS)]
        day = 8 + (i // len(STATIONS)) * 2
        n += inject_calibration_drift(df, sid, day_offset=day, length=96,
                                       max_bias=float(rng.uniform(1.5, 4.0)),
                                       jitter_min=0)
    counts["calibration_drift"] = n

    # ---- Power failures ----
    n = 0
    for i in range(cfg.power_failure):
        sid = STATIONS[i % len(STATIONS)]
        day = 12 + (i // len(STATIONS)) * 3
        n += inject_power_failure(df, sid, day_offset=day, length=4,
                                   jitter_min=int(rng.integers(0, 6)) * 15)
    counts["power_failure"] = n

    # ---- Multivariate inconsistency ----
    n = 0
    for i in range(cfg.multivariate_inconsistency):
        sid = STATIONS[i % len(STATIONS)]
        day = 15 + (i // len(STATIONS)) * 2
        n += inject_multivariate_inconsistency(df, sid, day_offset=day, length=6,
                                                jitter_min=int(rng.integers(0, 6)) * 15)
    counts["multivariate_inconsistency"] = n

    # ---- Missing data ----
    n = 0
    for i in range(cfg.missing_data):
        sid = STATIONS[i % len(STATIONS)]
        day = 18 + (i // len(STATIONS)) * 2
        n += inject_missing_data(df, sid, day_offset=day, length=8,
                                  jitter_min=int(rng.integers(0, 6)) * 15)
    counts["missing_data"] = n

    # ---- Normal weather events (not anomalies) ----
    n = 0
    for i in range(cfg.normal_weather_event // 4):
        day = 22 + (i % 3)
        n += inject_normal_weather_event(df, ["AWS_01", "AWS_02", "AWS_03"],
                                          day_offset=day, length=24,
                                          temp_shift=float(rng.uniform(-4.0, -2.0)),
                                          jitter_min=0)
    counts["normal_weather_event"] = n

    # ---- Sort and save ----
    df = df.sort_values(["timestamp", "station_id"]).reset_index(drop=True)
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False)

    # ---- Summary ----
    print("\n" + "=" * 60)
    print("INJECTION SUMMARY")
    print("=" * 60)
    total_anomalies = 0
    for k, v in counts.items():
        marker = " (not anomaly)" if k == "normal_weather_event" else ""
        print(f"  {k:30s}: {v:>5} rows{marker}")
        if k != "normal_weather_event":
            total_anomalies += v
    print("-" * 60)
    print(f"  Total injected anomaly rows : {total_anomalies}")
    print(f"  Total rows in file          : {len(df)}")
    print(f"  Saved to                    : {OUTPUT_PATH}")
    print("=" * 60)


if __name__ == "__main__":
    main()