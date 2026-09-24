"""
injector.py
SkyGuard AI - Controlled anomaly injection into the normal AWS dataset.

Reads:  data/normal_aws_data.csv
Writes: data/test_injected_aws.csv

Injects 8 anomaly scenarios into the normal data WITHOUT modifying the
original CSV. Adds ground-truth columns:
  - is_anomaly        : 1 = anomaly row, 0 = normal row
  - anomaly_type      : short label for the anomaly scenario
  - injected_parameter: which sensor/parameter was tampered with

GROUND-TRUTH COLUMNS ARE FOR EVALUATION ONLY. They must NEVER be used
as input features to an ML model.

NOTE: This is SYNTHETIC data for a hackathon prototype. The "power_failure"
signature (T/P/H all zero) is a SIMULATED PROTOTYPE signature, NOT a
universal real-world power-failure rule.
"""

import os
import numpy as np
import pandas as pd


# ----------------------------------------------------------------------
# Reproducibility: fix the random seed so injected anomaly timestamps
# are identical on every run. The seed controls small jitter on each
# scenario's start time so timestamps are not on predictable day
# boundaries, while day-level offsets remain hardcoded and distinct
# (so scenarios never overlap).
# ----------------------------------------------------------------------
RANDOM_SEED = 42
rng = np.random.default_rng(RANDOM_SEED)


# ----------------------------------------------------------------------
# Paths
# ----------------------------------------------------------------------
INPUT_PATH = "data/normal_aws_data.csv"
OUTPUT_PATH = "data/test_injected_aws.csv"


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def load_normal_data(path):
    """Read the normal AWS CSV; sort by station then timestamp."""
    df = pd.read_csv(path, parse_dates=["timestamp"])
    df = df.sort_values(["station_id", "timestamp"]).reset_index(drop=True)
    return df


def init_ground_truth(df):
    """Add empty ground-truth columns. Default: normal row."""
    df["is_anomaly"] = 0
    df["anomaly_type"] = "normal"
    df["injected_parameter"] = "none"
    return df


def _jitter_minutes(rng, max_steps=6):
    """Random jitter in 15-min steps, 0 to max_steps*15 minutes (seeded)."""
    return int(rng.integers(0, max_steps + 1)) * 15


def get_station_block(df, station_id, day_offset, length, jitter_min=0):
    """
    Return index labels for `length` consecutive observations of
    `station_id`, starting `day_offset` days after that station's first
    timestamp, plus `jitter_min` minutes of seeded jitter.

    Uses timestamps (not row positions) so the result is robust to prior
    row deletions on the same station (e.g. a missing-data injection).
    """
    sub = df[df["station_id"] == station_id].sort_values("timestamp")
    start_ts = (sub["timestamp"].iloc[0]
                + pd.Timedelta(days=day_offset)
                + pd.Timedelta(minutes=jitter_min))
    mask = sub["timestamp"] >= start_ts
    selected = sub[mask].head(length)
    return selected.index.to_numpy()


# ----------------------------------------------------------------------
# Anomaly injectors (one per scenario)
# ----------------------------------------------------------------------
def inject_temperature_spike(df, station_id, day_offset, length=5,
                              pattern=None, jitter_min=0):
    """Spike pattern: small up -> very high -> small down (triangle)."""
    if pattern is None:
        # Default 5-obs triangle: +3, +8, +15, +8, +3 (deg C).
        pattern = np.array([3.0, 8.0, 15.0, 8.0, 3.0])
    pattern = pattern[:length]
    idxs = get_station_block(df, station_id, day_offset, length, jitter_min)
    df.loc[idxs, "temperature"] = df.loc[idxs, "temperature"].to_numpy() + pattern
    df.loc[idxs, "is_anomaly"] = 1
    df.loc[idxs, "anomaly_type"] = "temperature_spike"
    df.loc[idxs, "injected_parameter"] = "temperature"
    return len(idxs)


def inject_temperature_drop(df, station_id, day_offset, length=5,
                            pattern=None, jitter_min=0):
    """Drop pattern: small down -> very low -> small up (inverted triangle)."""
    if pattern is None:
        pattern = -np.array([3.0, 8.0, 15.0, 8.0, 3.0])
    pattern = pattern[:length]
    idxs = get_station_block(df, station_id, day_offset, length, jitter_min)
    df.loc[idxs, "temperature"] = df.loc[idxs, "temperature"].to_numpy() + pattern
    df.loc[idxs, "is_anomaly"] = 1
    df.loc[idxs, "anomaly_type"] = "temperature_drop"
    df.loc[idxs, "injected_parameter"] = "temperature"
    return len(idxs)


def inject_frozen_sensor(df, station_id, day_offset, length=24,
                         variable="temperature", jitter_min=0):
    """
    Freeze `variable` at its first value in the block for `length`
    consecutive observations. Only this frozen block is labelled as an
    anomaly; incidental repeated values elsewhere in the data (which
    should not occur given the generator's noise) are NOT labelled.
    """
    idxs = get_station_block(df, station_id, day_offset, length, jitter_min)
    frozen_value = df.loc[idxs[0], variable]
    df.loc[idxs, variable] = frozen_value
    df.loc[idxs, "is_anomaly"] = 1
    df.loc[idxs, "anomaly_type"] = "frozen_sensor"
    df.loc[idxs, "injected_parameter"] = variable
    return len(idxs)


def inject_calibration_drift(df, station_id, day_offset, length=96,
                             max_bias=4.0, jitter_min=0):
    """Gradually add a temperature bias over `length` observations (linear ramp)."""
    idxs = get_station_block(df, station_id, day_offset, length, jitter_min)
    bias = np.linspace(0.0, max_bias, length)
    df.loc[idxs, "temperature"] = df.loc[idxs, "temperature"].to_numpy() + bias
    df.loc[idxs, "is_anomaly"] = 1
    df.loc[idxs, "anomaly_type"] = "calibration_drift"
    df.loc[idxs, "injected_parameter"] = "temperature"
    return len(idxs)


def inject_missing_data(df, station_id, day_offset, length=12, jitter_min=0):
    """
    Delete `length` consecutive observations for `station_id`, creating a
    REAL timestamp gap. The deleted rows cannot carry a label since they
    no longer exist; the ground truth is the timestamp gap itself.
    Returns the number of rows deleted (for the summary).
    """
    idxs = get_station_block(df, station_id, day_offset, length, jitter_min)
    df.drop(index=idxs, inplace=True)
    return length


def inject_power_failure(df, station_id, day_offset, length=4, jitter_min=0):
    """
    Set T/P/H to zero for `length` observations.
    This is a SIMULATED PROTOTYPE signature (T=P=H=0), NOT a universal
    real-world power-failure rule.
    """
    idxs = get_station_block(df, station_id, day_offset, length, jitter_min)
    df.loc[idxs, ["temperature", "pressure", "humidity"]] = 0.0
    df.loc[idxs, "is_anomaly"] = 1
    df.loc[idxs, "anomaly_type"] = "power_failure"
    df.loc[idxs, "injected_parameter"] = "all"
    return len(idxs)


def inject_multivariate_inconsistency(df, station_id, day_offset, length=6,
                                       variable="humidity", magnitude_pct=0.30,
                                       jitter_min=0):
    """
    Make ONE variable abnormal while the other two stay comparatively
    stable. Implemented as a multiplicative bump on `variable` only.
    """
    idxs = get_station_block(df, station_id, day_offset, length, jitter_min)
    bumped = df.loc[idxs, variable].to_numpy() * (1.0 + magnitude_pct)
    if variable == "humidity":
        bumped = np.clip(bumped, None, 99.0)  # keep RH physically plausible
    df.loc[idxs, variable] = bumped
    df.loc[idxs, "is_anomaly"] = 1
    df.loc[idxs, "anomaly_type"] = "multivariate_inconsistency"
    df.loc[idxs, "injected_parameter"] = variable
    return len(idxs)


def inject_normal_weather_event(df, station_ids, day_offset, length=48,
                                temp_shift=-3.0, jitter_min=0):
    """
    A genuine weather event (e.g. a cold front) affecting several nearby
    stations at roughly the same time. This is NOT labelled as a sensor
    anomaly: is_anomaly stays 0, anomaly_type = normal_weather_event.
    """
    n_rows = 0
    for sid in station_ids:
        idxs = get_station_block(df, sid, day_offset, length, jitter_min)
        df.loc[idxs, "temperature"] = df.loc[idxs, "temperature"].to_numpy() + temp_shift
        df.loc[idxs, "anomaly_type"] = "normal_weather_event"
        df.loc[idxs, "injected_parameter"] = "temperature"
        # is_anomaly stays 0 (already initialized to 0 in init_ground_truth).
        n_rows += len(idxs)
    return n_rows


# ----------------------------------------------------------------------
# Main pipeline
# ----------------------------------------------------------------------
def main():
    if not os.path.exists(INPUT_PATH):
        raise FileNotFoundError(
            f"Input not found: {INPUT_PATH}. Run generator.py first."
        )

    # Load and initialize ground-truth columns.
    df = load_normal_data(INPUT_PATH)
    df = init_ground_truth(df)

    # Track counts per scenario for the summary.
    counts = {}

    # --------------------------------------------------------------
    # Inject each scenario in a distinct, non-overlapping time window.
    # Day offsets are per-station (each station has 30 days of data,
    # 96 obs/day, so day_offset*96 + length must stay < 2880).
    # Small seeded jitter (0-90 min, in 15-min steps) is added to each
    # scenario's start time so exact timestamps are not on predictable
    # day boundaries.
    # --------------------------------------------------------------

    # 1) Temperature spike (AWS_01, around day 2, 5 obs).
    counts["temperature_spike"] = inject_temperature_spike(
        df, "AWS_01", day_offset=2, length=5,
        jitter_min=_jitter_minutes(rng))

    # 2) Temperature drop (AWS_02, around day 5, 5 obs).
    counts["temperature_drop"] = inject_temperature_drop(
        df, "AWS_02", day_offset=5, length=5,
        jitter_min=_jitter_minutes(rng))

    # 3) Frozen sensor (AWS_03, around day 8, 24 obs = 6h, temperature frozen).
    counts["frozen_sensor"] = inject_frozen_sensor(
        df, "AWS_03", day_offset=8, length=24, variable="temperature",
        jitter_min=_jitter_minutes(rng))

    # 4) Calibration drift (AWS_04, around day 11, 96 obs = 24h, +4C ramp).
    counts["calibration_drift"] = inject_calibration_drift(
        df, "AWS_04", day_offset=11, length=96, max_bias=4.0,
        jitter_min=_jitter_minutes(rng))

    # 5) Missing data (AWS_05, around day 15, 12 obs = 3h physically deleted).
    counts["missing_data"] = inject_missing_data(
        df, "AWS_05", day_offset=15, length=12,
        jitter_min=_jitter_minutes(rng))

    # 6) Power failure (AWS_01, around day 18, 4 obs = 1h of T=P=H=0).
    counts["power_failure"] = inject_power_failure(
        df, "AWS_01", day_offset=18, length=4,
        jitter_min=_jitter_minutes(rng))

    # 7) Multivariate inconsistency (AWS_03, around day 21, 6 obs, humidity +30%).
    counts["multivariate_inconsistency"] = inject_multivariate_inconsistency(
        df, "AWS_03", day_offset=21, length=6, variable="humidity",
        magnitude_pct=0.30, jitter_min=_jitter_minutes(rng))

    # 8) Genuine weather event (AWS_01 + AWS_02 + AWS_05, around day 25,
    #    48 obs = 12h cold front, -3C). NOT labelled as anomaly.
    counts["normal_weather_event"] = inject_normal_weather_event(
        df, ["AWS_01", "AWS_02", "AWS_05"], day_offset=25, length=48,
        temp_shift=-3.0, jitter_min=_jitter_minutes(rng))

    # --------------------------------------------------------------
    # Final sort and save.
    # --------------------------------------------------------------
    df = df.sort_values(["timestamp", "station_id"]).reset_index(drop=True)
    df.to_csv(OUTPUT_PATH, index=False)

    # --------------------------------------------------------------
    # Summary printout.
    # --------------------------------------------------------------
    print("=" * 60)
    print("SkyGuard AI - Anomaly injection complete")
    print("=" * 60)
    print(f"Input file        : {INPUT_PATH}")
    print(f"Output file       : {OUTPUT_PATH}")
    print(f"Total rows (out)  : {len(df)}")
    print(f"Original rows (in): {len(df) + counts['missing_data']}")
    print(f"Random seed       : {RANDOM_SEED}")
    print("-" * 60)
    print("Anomaly summary (rows affected per scenario):")
    for k, v in counts.items():
        print(f"  {k:30s}: {v}")
    print("-" * 60)
    n_anom = int((df["is_anomaly"] == 1).sum())
    n_normal = int((df["is_anomaly"] == 0).sum())
    print(f"Rows with is_anomaly=1 (anomalies)              : {n_anom}")
    print(f"Rows with is_anomaly=0 (normal + weather event) : {n_normal}")
    print("-" * 60)
    print("Anomaly type distribution in output CSV:")
    print(df["anomaly_type"].value_counts().to_string())
    print("-" * 60)
    print("Reminder:")
    print("  * Ground-truth columns (is_anomaly, anomaly_type,")
    print("    injected_parameter) are for EVALUATION ONLY.")
    print("  * They must NEVER be used as ML input features.")


if __name__ == "__main__":
    main()